const flag = globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean };

/**
 * Do something at the one instant a browser reaches and `act()` hides: AFTER
 * React has committed a render to the DOM, but BEFORE it has run that commit's
 * passive effects.
 *
 * React defers passive effects to a task of their own, so in a browser that gap
 * is real and a user's tap lands in it whenever the device is busy. Inside
 * `act()` it does not exist — act drains renders and effects from one queue, so
 * every effect appears to run before the next event can arrive. That is why a
 * defect living in this gap passes locally and fails on a loaded CI runner.
 *
 * `commit` is what paints (settling a fetch the page is waiting on). `then` runs
 * from a MutationObserver callback — a microtask fired by the commit's own DOM
 * mutation, which is inside the gap because the effect flush is a later task.
 * The act environment is off for the duration: with it on, React would route the
 * work back through act's queue and close the gap again.
 */
export async function inPaintGap(commit: () => void, then: () => void): Promise<void> {
  const previous = flag.IS_REACT_ACT_ENVIRONMENT;
  flag.IS_REACT_ACT_ENVIRONMENT = false;
  const observer = new MutationObserver(() => {
    observer.disconnect();
    then();
  });
  try {
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    });
    commit();
    // Long enough for the deferred effect flush, the render it preempted and
    // any focus move either of them makes.
    await new Promise((resolve) => setTimeout(resolve, 50));
  } finally {
    observer.disconnect();
    flag.IS_REACT_ACT_ENVIRONMENT = previous;
  }
}
