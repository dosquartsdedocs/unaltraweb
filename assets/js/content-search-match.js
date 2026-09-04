(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UnaltrawebContentSearchMatch = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var MARK_RE = /\p{M}/gu;
  var WORD_RE = /[\p{L}\p{N}]/u;

  function foldWithMap(value) {
    var source = (value || "").toString();
    var folded = "";
    var starts = [];
    var ends = [];

    for (var index = 0; index < source.length;) {
      var codePoint = source.codePointAt(index);
      var character = String.fromCodePoint(codePoint);
      var end = index + character.length;
      var normalized = character.toLowerCase().normalize("NFD").replace(MARK_RE, "");

      if (!normalized) {
        if (ends.length) ends[ends.length - 1] = end;
        index = end;
        continue;
      }

      for (var offset = 0; offset < normalized.length; offset += 1) {
        var unit = normalized[offset];
        if (/\s/u.test(unit)) {
          if (folded.endsWith(" ")) {
            ends[ends.length - 1] = end;
            continue;
          }
          unit = " ";
        }
        folded += unit;
        starts.push(index);
        ends.push(end);
      }
      index = end;
    }

    return { text: folded, starts: starts, ends: ends };
  }

  function normalize(value) {
    return foldWithMap(value).text.trim();
  }

  function collapseWhitespaceWithMap(value) {
    var source = (value || "").toString();
    var text = "";
    var starts = [];
    var ends = [];

    for (var index = 0; index < source.length;) {
      var codePoint = source.codePointAt(index);
      var character = String.fromCodePoint(codePoint);
      var end = index + character.length;
      if (/\s/u.test(character)) {
        if (text && !text.endsWith(" ")) {
          text += " ";
          starts.push(index);
          ends.push(end);
        } else if (text.endsWith(" ")) {
          ends[ends.length - 1] = end;
        }
      } else {
        text += character;
        for (var offset = 0; offset < character.length; offset += 1) {
          starts.push(index);
          ends.push(end);
        }
      }
      index = end;
    }

    if (text.endsWith(" ")) {
      text = text.slice(0, -1);
      starts.pop();
      ends.pop();
    }
    return { text: text, starts: starts, ends: ends };
  }

  function codePointBefore(value, index) {
    if (index <= 0) return "";
    var points = Array.from(value.slice(0, index));
    return points[points.length - 1] || "";
  }

  function codePointAt(value, index) {
    return Array.from(value.slice(index))[0] || "";
  }

  function isWordCharacter(value) {
    return Boolean(value && WORD_RE.test(value));
  }

  function hasWordBoundaries(source, start, end, needle) {
    var needlePoints = Array.from(needle);
    if (isWordCharacter(needlePoints[0]) && isWordCharacter(codePointBefore(source, start))) return false;
    if (isWordCharacter(needlePoints[needlePoints.length - 1]) && isWordCharacter(codePointAt(source, end))) return false;
    return true;
  }

  function findOccurrences(value, query) {
    var source = (value || "").toString();
    var folded = foldWithMap(source);
    var needle = normalize(query);
    var matches = [];
    if (!needle) return matches;

    var cursor = 0;
    while (cursor <= folded.text.length - needle.length) {
      var found = folded.text.indexOf(needle, cursor);
      if (found < 0) break;
      var foldedEnd = found + needle.length;
      if (hasWordBoundaries(folded.text, found, foldedEnd, needle)) {
        matches.push({
          start: folded.starts[found],
          end: folded.ends[foldedEnd - 1]
        });
        cursor = foldedEnd;
      } else {
        cursor = found + 1;
      }
    }
    return matches;
  }

  function excerptParts(value, occurrence, before, after) {
    var source = (value || "").toString();
    var start = Math.max(0, occurrence.start - (before || 72));
    var end = Math.min(source.length, occurrence.end + (after || 112));
    if (start > 0) {
      var nextSpace = source.indexOf(" ", start);
      if (nextSpace >= 0 && nextSpace < occurrence.start) start = nextSpace + 1;
    }
    if (end < source.length) {
      var previousSpace = source.lastIndexOf(" ", end);
      if (previousSpace > occurrence.end) end = previousSpace;
    }
    return {
      before: (start > 0 ? "..." : "") + source.slice(start, occurrence.start),
      match: source.slice(occurrence.start, occurrence.end),
      after: source.slice(occurrence.end, end) + (end < source.length ? "..." : "")
    };
  }

  return {
    normalize: normalize,
    collapseWhitespaceWithMap: collapseWhitespaceWithMap,
    findOccurrences: findOccurrences,
    excerptParts: excerptParts
  };
});
