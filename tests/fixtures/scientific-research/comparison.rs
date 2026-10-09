// Scientific output comparison used by a research kernel's acceptance check.
// Contract: equally sized, finite scalar arrays; tolerance is nonnegative.
// Every candidate value must be within the agreed absolute error bound.
pub fn within_tolerance(candidate: &[f64], reference: &[f64], tolerance: f64) -> bool {
    for (actual, expected) in candidate.iter().zip(reference) {
        if (actual - expected).abs() > tolerance {
            return false;
        }
    }
    true
}
