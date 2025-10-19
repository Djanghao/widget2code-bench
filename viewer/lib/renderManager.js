const activeRenders = new Map();
const renderControllers = new Map();

export function isRenderActive(key) {
  return activeRenders.has(key);
}

export function setRenderActive(key, promise, controller = null) {
  activeRenders.set(key, promise);
  if (controller) {
    renderControllers.set(key, controller);
  }
}

export function deleteRenderActive(key) {
  activeRenders.delete(key);
  renderControllers.delete(key);
}

export function stopRender(key) {
  const controller = renderControllers.get(key);
  if (controller) {
    controller.abort();
    deleteRenderActive(key);
    return true;
  }
  return false;
}

export function getActiveRenders() {
  return Array.from(activeRenders.keys());
}
