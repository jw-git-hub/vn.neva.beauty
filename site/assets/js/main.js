import { initHeader } from './components/header.js';
import { initMetrika } from './components/metrika.js';

document.addEventListener('DOMContentLoaded', () => {
  initMetrika();
  initHeader();
});
