# INFRASTRUCTURE
INTERACTIVE_CANDIDATE_SELECTOR = "input[type=checkbox], input[type=radio], [role=checkbox], button, label"


# FUNCTIONS

async def cdp_get_document_root(cdp) -> int:
    response = await cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
    return response["root"]["nodeId"]


async def cdp_query_selector(cdp, root_node_id: int, selector: str) -> int | None:
    try:
        response = await cdp.send("DOM.querySelector", {"nodeId": root_node_id, "selector": selector})
    except Exception:
        return None
    return response.get("nodeId") or None


async def cdp_describe_node(cdp, node_id: int) -> dict:
    response = await cdp.send("DOM.describeNode", {"nodeId": node_id, "depth": 1, "pierce": True})
    return response.get("node", {})


async def cdp_find_widget_node(cdp) -> int | None:
    root_node_id = await cdp_get_document_root(cdp)
    return await cdp_query_selector(cdp, root_node_id, "altcha-widget")


async def cdp_shadow_root_node(cdp, widget_node_id: int) -> tuple[int | None, str | None]:
    node = await cdp_describe_node(cdp, widget_node_id)
    shadow_roots = node.get("shadowRoots") or []
    if not shadow_roots:
        return None, None
    shadow = shadow_roots[0]
    mode = shadow.get("shadowRootType")
    backend_node_id = shadow.get("backendNodeId")
    if backend_node_id is None:
        return None, mode
    response = await cdp.send("DOM.pushNodesByBackendIdsToFrontend", {"backendNodeIds": [backend_node_id]})
    node_ids = response.get("nodeIds") or []
    return (node_ids[0] if node_ids else None), mode


async def cdp_click_node(cdp, node_id: int) -> None:
    box = await cdp.send("DOM.getBoxModel", {"nodeId": node_id})
    quad = box["model"]["content"]
    x = (quad[0] + quad[2] + quad[4] + quad[6]) / 4
    y = (quad[1] + quad[3] + quad[5] + quad[7]) / 4
    await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})


async def locate_interactive_element(cdp, widget_node_id: int) -> dict:
    shadow_node_id, shadow_mode = await cdp_shadow_root_node(cdp, widget_node_id)
    target_node_id = None
    used_selector = None
    if shadow_node_id is not None:
        target_node_id = await cdp_query_selector(cdp, shadow_node_id, INTERACTIVE_CANDIDATE_SELECTOR)
        if target_node_id is not None:
            used_selector = f"shadowRoot: {INTERACTIVE_CANDIDATE_SELECTOR}"
    if target_node_id is None:
        target_node_id = await cdp_query_selector(cdp, widget_node_id, INTERACTIVE_CANDIDATE_SELECTOR)
        if target_node_id is not None:
            used_selector = f"light DOM: {INTERACTIVE_CANDIDATE_SELECTOR}"
    if target_node_id is None:
        target_node_id = widget_node_id
        used_selector = "altcha-widget host (no interactive descendant found)"
    target_node = await cdp_describe_node(cdp, target_node_id)
    return {
        "shadow_mode": shadow_mode,
        "used_selector": used_selector,
        "target_tag": (target_node.get("nodeName") or "").lower(),
        "target_node_id": target_node_id,
    }
