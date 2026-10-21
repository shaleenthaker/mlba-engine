//! Balatro simulator core for the MLBA engine.
//!
//! State is a pure function of (seed, deck, stake, actions). See
//! docs/design.md for the full spec.

pub mod content;
pub mod mlba;
pub mod replay;
pub mod rng;
pub mod rules;

/// Game version the simulator targets (vanilla Lua, patched by Steamodded).
pub const GAME_VERSION: &str = "1.0.1o";

/// Steamodded version whose scoring pipeline is ground truth.
pub const SMODS_VERSION: &str = "26.1002.0";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn versions_are_pinned() {
        assert_eq!(GAME_VERSION, "1.0.1o");
        assert_eq!(SMODS_VERSION, "26.1002.0");
    }
}
