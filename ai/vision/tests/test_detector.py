"""Pruebas de transformación de resultados sin cargar un modelo."""

import unittest

from detector import _to_detections


class Value:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class Coordinates:
    def tolist(self):
        return [1, 2, 30, 40]


class Box:
    cls = Value(0)
    conf = Value(0.9)
    xyxy = [Coordinates()]


class Result:
    boxes = [Box()]
    names = {0: "person"}


class DetectorConversionTests(unittest.TestCase):
    def test_converts_ultralytics_box_to_structured_detection(self):
        detections = _to_detections(Result())

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].class_name, "person")
        self.assertEqual(detections[0].bounding_box.x2, 30.0)

