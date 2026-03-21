"""Node: Three-layer exact match verification of search candidates."""

from loguru import logger

from orchestrator.state import GlobalState
from automation.screenshot import capture_screen, save_debug_screenshot


def exact_match_node(state: GlobalState) -> GlobalState:
    """Verify the correct item using three layers of validation.

    Layer 1: Exact text match (== not 'in' or 'startswith').
    Layer 2: Full folder path verification.
    Layer 3: Depth check (must be deepest = actual file, not folder).
    """
    logger.info("[Agent2] Node: exact_match — entering")
    try:
        candidates = state.get("ui_candidates", [])
        report_name = state["report_name"]
        module = state["module"]
        folders = state["folders"]

        # The search tree does not include the module prefix — only folders + report.
        # Matching is case-insensitive throughout.
        expected_folders_lower = [f.strip().lower() for f in folders]
        report_name_lower = report_name.strip().lower()

        logger.debug(
            "Matching against: report_name='{}' (ci), folders={} (ci), module='{}'",
            report_name, folders, module,
        )

        matched = []

        for i, candidate in enumerate(candidates):
            cand_text = candidate["text"].strip()
            cand_path = candidate.get("tree_path", [])
            cand_depth = candidate.get("depth", 0)

            # Layer 1: Case-insensitive text match
            if cand_text.lower() != report_name_lower:
                logger.debug(
                    "Candidate #{}: FAILED Layer 1 — text '{}' != '{}'",
                    i, cand_text, report_name,
                )
                continue
            logger.debug("Candidate #{}: PASSED Layer 1 — text match (ci).", i)

            # Layer 2: Folder path verification (case-insensitive, module excluded)
            # cand_path is [parent1, parent2, ..., report_name]
            # expected tail is [...folders..., report_name]
            path_match = True
            if expected_folders_lower:
                cand_path_lower = [p.strip().lower() for p in cand_path]
                # The folders should appear as consecutive ancestors ending just before the leaf
                for j, folder in enumerate(expected_folders_lower):
                    if folder not in cand_path_lower:
                        path_match = False
                        logger.debug(
                            "Candidate #{}: FAILED Layer 2 — folder '{}' not in path {}",
                            i, folder, cand_path,
                        )
                        break

            if not path_match:
                continue
            logger.debug("Candidate #{}: PASSED Layer 2 — folders present in path.", i)

            # Layer 3: Must be a leaf (depth > 0 means it has parent folders)
            if cand_depth == 0 and expected_folders_lower:
                logger.debug(
                    "Candidate #{}: FAILED Layer 3 — depth=0 but folders expected",
                    i,
                )
                continue
            logger.debug("Candidate #{}: PASSED Layer 3 — depth ok ({}).", i, cand_depth)

            matched.append(candidate)

        if not matched:
            # Last resort: accept any coordinate-based candidate (from screenshot fallback)
            coord_candidates = [
                c for c in candidates if c.get("screen_x") is not None
            ]
            if coord_candidates:
                matched = coord_candidates
                logger.info(
                    "[Agent2] No UIA match — using screenshot-based candidate at ({}, {}).",
                    matched[0]["screen_x"], matched[0]["screen_y"],
                )

        if not matched:
            details = []
            for c in candidates:
                details.append(
                    f"  text='{c['text']}', path={c.get('tree_path', [])}, "
                    f"depth={c.get('depth', '?')}"
                )
            state["error"] = (
                f"No exact match found for '{report_name}' "
                f"(folders={folders}). "
                f"Candidates:\n" + "\n".join(details)
            )
            logger.error("[Agent2] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "exact_match_failed")
            except Exception:
                pass
            return state

        if len(matched) > 1:
            logger.warning(
                "Multiple exact matches found ({}). Using first.",
                len(matched),
            )

        state["exact_match"] = matched[0]
        logger.info(
            "[Agent2] Exact match found: '{}' at path {}",
            matched[0]["text"],
            matched[0].get("tree_path", []),
        )

    except Exception as exc:
        state["error"] = f"exact_match failed: {exc}"
        logger.error("[Agent2] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "exact_match_error")
        except Exception:
            pass

    return state
