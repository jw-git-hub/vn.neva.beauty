let count = 0;

export function lockScroll() {
  if (count === 0) {
    document.body.classList.add('no-scroll');
  }
  count++;
}

export function unlockScroll() {
  if (count === 0) return;
  count--;
  if (count === 0) {
    document.body.classList.remove('no-scroll');
  }
}

export function resetScrollLock() {
  count = 0;
  document.body.classList.remove('no-scroll');
}
