"""Cached liveness predictor around the vendored Silent-Face-Anti-Spoofing code.

The upstream `test.py` reloads each model from disk on every prediction; for a
long-running service we load the two anti-spoof models (and the caffe face
detector) once at startup and reuse them. Paths are resolved absolutely so the
service does not depend on the process working directory.
"""
import math
import os
import sys
from collections import OrderedDict

import cv2
import numpy as np
import torch
import torch.nn.functional as F

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
sys.path.insert(0, VENDOR)

from src.data_io import transform as trans  # noqa: E402
from src.generate_patches import CropImage  # noqa: E402
from src.model_lib.MiniFASNet import (  # noqa: E402
    MiniFASNetV1,
    MiniFASNetV1SE,
    MiniFASNetV2,
    MiniFASNetV2SE,
)
from src.utility import get_kernel, parse_model_name  # noqa: E402

MODEL_MAPPING = {
    "MiniFASNetV1": MiniFASNetV1,
    "MiniFASNetV2": MiniFASNetV2,
    "MiniFASNetV1SE": MiniFASNetV1SE,
    "MiniFASNetV2SE": MiniFASNetV2SE,
}

DETECTION_DIR = os.path.join(VENDOR, "resources", "detection_model")
MODEL_DIR = os.path.join(VENDOR, "resources", "anti_spoof_models")


class LivenessPredictor:
    def __init__(self, model_dir=MODEL_DIR, detection_dir=DETECTION_DIR, device_id=0):
        self.device = torch.device(
            f"cuda:{device_id}" if torch.cuda.is_available() else "cpu"
        )
        self.detector = cv2.dnn.readNetFromCaffe(
            os.path.join(detection_dir, "deploy.prototxt"),
            os.path.join(detection_dir, "Widerface-RetinaFace.caffemodel"),
        )
        self.detector_confidence = 0.6
        self.cropper = CropImage()
        self.transform = trans.Compose([trans.ToTensor()])

        # Preload every anti-spoof model once. The final score is the mean of the
        # per-model softmax outputs (upstream sums them; we normalise by count).
        self.models = []
        for name in sorted(os.listdir(model_dir)):
            if not name.endswith(".pth"):
                continue
            h_input, w_input, model_type, scale = parse_model_name(name)
            kernel = get_kernel(h_input, w_input)
            model = MODEL_MAPPING[model_type](conv6_kernel=kernel).to(self.device)
            state_dict = torch.load(os.path.join(model_dir, name), map_location=self.device)
            if next(iter(state_dict)).startswith("module."):
                state_dict = OrderedDict((k[7:], v) for k, v in state_dict.items())
            model.load_state_dict(state_dict)
            model.eval()
            self.models.append(
                {"model": model, "scale": scale, "w": w_input, "h": h_input, "name": name}
            )
        if not self.models:
            raise RuntimeError(f"No .pth anti-spoof models found in {model_dir}")

    def _detect_face(self, img):
        """Return (bbox[x,y,w,h], confidence) of the highest-confidence face."""
        height, width = img.shape[:2]
        aspect = width / height
        det_img = img
        if width * height >= 192 * 192:
            det_img = cv2.resize(
                img,
                (int(192 * math.sqrt(aspect)), int(192 / math.sqrt(aspect))),
                interpolation=cv2.INTER_LINEAR,
            )
        blob = cv2.dnn.blobFromImage(det_img, 1, mean=(104, 117, 123))
        self.detector.setInput(blob, "data")
        out = self.detector.forward("detection_out").squeeze()
        idx = int(np.argmax(out[:, 2]))
        conf = float(out[idx, 2])
        left, top = out[idx, 3] * width, out[idx, 4] * height
        right, bottom = out[idx, 5] * width, out[idx, 6] * height
        bbox = [int(left), int(top), int(right - left + 1), int(bottom - top + 1)]
        return bbox, conf

    @torch.no_grad()
    def predict(self, img):
        bbox, conf = self._detect_face(img)
        if conf < self.detector_confidence:
            return {
                "is_live": False,
                "score": 0.0,
                "label": None,
                "face_detected": False,
                "detector_confidence": round(conf, 4),
            }

        prediction = np.zeros((1, 3))
        for m in self.models:
            patch = self.cropper.crop(
                org_img=img,
                bbox=bbox,
                scale=m["scale"],
                out_w=m["w"],
                out_h=m["h"],
                crop=m["scale"] is not None,
            )
            tensor = self.transform(patch).unsqueeze(0).to(self.device)
            out = m["model"].forward(tensor)
            prediction += F.softmax(out, dim=1).cpu().numpy()

        label = int(np.argmax(prediction))
        real_score = float(prediction[0][1] / len(self.models))  # label 1 == real
        return {
            "is_live": label == 1,
            "score": round(real_score, 4),
            "label": label,
            "face_detected": True,
            "detector_confidence": round(conf, 4),
            "bbox": bbox,
        }
