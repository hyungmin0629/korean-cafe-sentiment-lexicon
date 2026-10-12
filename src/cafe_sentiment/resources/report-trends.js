"use strict";
const CafeTrends = (() => {
  function adjacent(left, right) {
    if (!left || !right) return false;
    const index = value => Number(value.slice(0, 4)) * 12 + Number(value.slice(5, 7));
    return index(right.period) - index(left.period) === 1;
  }
  function comparable(left, right, minimum) {
    return adjacent(left, right) && [left, right].every(row =>
      row.score != null && row.scored_reviews >= minimum);
  }
  function summarize(rows, minimum) {
    const last = rows.at(-1), previous = rows.at(-2);
    const changes = rows.slice(1).map((row, i) => comparable(rows[i], row, minimum) ?
      {from: rows[i].period, to: row.period, delta: row.score - rows[i].score} : null).filter(Boolean);
    const largest = changes.reduce((best, item) => !best || Math.abs(item.delta) > Math.abs(best.delta) ? item : best, null);
    return {last, previous, delta: comparable(previous, last, minimum) ? last.score - previous.score : null, largest};
  }
  return {adjacent, comparable, summarize};
})();
