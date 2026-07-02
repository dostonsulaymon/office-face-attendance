#!/usr/bin/env bash
# End-to-end backend business-rule smoke test (Slice 4 verification).
set -uo pipefail
API=http://localhost:8901
F="$(cd "$(dirname "$0")" && pwd)/test-faces"
KEY=00000000-0000-0000-0000-000000000002   # demo recognition key
pass(){ echo "  ✅ $1"; }
fail(){ echo "  ❌ $1"; }

echo "0. cleanup slice-2 Person_A subject"
curl -sS -X DELETE "http://localhost:8900/api/v1/recognition/subjects/Person_A" -H "x-api-key: $KEY" >/dev/null

echo "1. login"
TOKEN=$(curl -sS -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"change-me-admin-password"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
[ -n "$TOKEN" ] && pass "got JWT" || { fail "login"; exit 1; }
AUTH="Authorization: Bearer $TOKEN"

echo "2. register devices"
CI=$(curl -sS -X POST "$API/api/devices" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"device_id":"entrance-01","role":"CHECK_IN","label":"Entrance"}')
CIKEY=$(echo "$CI" | python3 -c 'import sys,json;print(json.load(sys.stdin)["api_key"])')
CO=$(curl -sS -X POST "$API/api/devices" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"device_id":"exit-01","role":"CHECK_OUT","label":"Exit"}')
COKEY=$(echo "$CO" | python3 -c 'import sys,json;print(json.load(sys.stdin)["api_key"])')
[ -n "$CIKEY" ] && [ -n "$COKEY" ] && pass "checkin+checkout devices registered" || fail "device reg"

echo "3. enroll employee EMP-A (2 reference photos)"
ENR=$(curl -sS -X POST "$API/api/employees" -H "$AUTH" \
  -F "employee_code=EMP-A" -F "full_name=Alex Anderson" -F "department=Engineering" \
  -F "photos=@$F/001_A.jpg" -F "photos=@$F/003_A.jpg")
echo "   -> $ENR"
echo "$ENR" | grep -q '"employee_code":"EMP-A"' && pass "enrolled" || fail "enroll"

evt(){ # $1=devkey  $2=image ; prints response
  curl -sS -X POST "$API/api/attendance/event" \
    -H "X-Device-Id: $3" -H "X-Device-Key: $1" -F "image=@$F/$2"
}

echo "4. check-in with a DIFFERENT photo of A (002_A)"
R=$(evt "$CIKEY" 002_A.jpg entrance-01); echo "   -> $R"
echo "$R" | grep -q '"event_type":"checkin"' && pass "checked in" || fail "checkin"

echo "5. immediate re-scan on same device -> cooldown"
R=$(evt "$CIKEY" 002_A.jpg entrance-01); echo "   -> $R"
echo "$R" | grep -qi 'moment ago' && pass "cooldown enforced" || fail "cooldown"

echo "6. today -> currently_in should be 1"
T=$(curl -sS "$API/api/attendance/today" -H "$AUTH"); echo "   -> $T"
echo "$T" | grep -q '"currently_in":1' && pass "headcount=1" || fail "headcount"

echo "7. check-out on exit device"
R=$(evt "$COKEY" 002_A.jpg exit-01); echo "   -> $R"
echo "$R" | grep -q '"event_type":"checkout"' && pass "checked out" || fail "checkout"

echo "8. today -> currently_in should be 0, status closed"
T=$(curl -sS "$API/api/attendance/today" -H "$AUTH"); echo "   -> $T"
echo "$T" | grep -q '"currently_in":0' && pass "headcount=0" || fail "headcount0"

echo "9. stranger (007_B) at entrance -> not recognized"
R=$(evt "$CIKEY" 007_B.jpg entrance-01); echo "   -> $R"
echo "$R" | grep -q '"matched":false' && pass "stranger rejected" || fail "stranger"

echo "done."
