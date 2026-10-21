//! Python bindings for the MLBA simulator.

use pyo3::prelude::*;

#[pymodule]
mod mlba_sim {
    use pyo3::prelude::*;

    /// Game version the simulator targets.
    #[pyfunction]
    fn game_version() -> &'static str {
        ::mlba_sim::GAME_VERSION
    }

    /// Steamodded version whose scoring pipeline is ground truth.
    #[pyfunction]
    fn smods_version() -> &'static str {
        ::mlba_sim::SMODS_VERSION
    }
}
