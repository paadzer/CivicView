"""Evaluation metrics (synthetic DBSCAN + coordinate rules)."""

import numpy as np
from django.test import TestCase

from civicview.evaluation.metrics import (
    coordinate_validation_matrix,
    evaluate_dbscan_on_points,
    run_synthetic_clustering_evaluation,
    validate_wgs84_and_ireland,
)


class CoordinateValidationTests(TestCase):
    def test_dublin_accepted(self):
        ok, errs = validate_wgs84_and_ireland(53.3498, -6.2603)
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_london_rejected_for_ireland(self):
        ok, errs = validate_wgs84_and_ireland(51.5, -0.12)
        self.assertFalse(ok)
        # London lat is still inside Ireland lat band; lon fails east bound
        self.assertIn("ireland_longitude", errs)

    def test_matrix_all_match_expectation(self):
        matrix = coordinate_validation_matrix()
        for row in matrix:
            self.assertTrue(
                row["matches_expectation"],
                msg=f"Case {row['name']}: ok={row['ok']} expected {row['expect_ok']}",
            )


class SyntheticClusteringTests(TestCase):
    def test_grid_forms_single_cluster_under_defaults(self):
        result = run_synthetic_clustering_evaluation(eps_meters=250, min_samples=5)
        self.assertEqual(result["n_clusters"], 1)
        self.assertEqual(result["noise_count"], 0)
        self.assertEqual(result["n_points"], 25)

    def test_evaluate_dbscan_noise_when_eps_tiny(self):
        coords = np.array([[0, 0], [1000, 0], [2000, 0]], dtype=np.float64)
        r = evaluate_dbscan_on_points(coords, eps_meters=10, min_samples=2)
        self.assertEqual(r["n_clusters"], 0)
        self.assertEqual(r["noise_count"], 3)
