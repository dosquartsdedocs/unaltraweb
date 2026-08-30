"use strict";

var assert = require("node:assert/strict");
var test = require("node:test");
var matcher = require("../../assets/js/content-search-match.js");

test("returns every repeated occurrence", function () {
  var source = "Terra terra i més terra.";
  var matches = matcher.findOccurrences(source, "terra");

  assert.equal(matches.length, 3);
  assert.deepEqual(matches.map(function (match) { return source.slice(match.start, match.end); }), ["Terra", "terra", "terra"]);
});

test("matches composed and decomposed diacritics with source offsets", function () {
  var source = "Café cafe\u0301 CAFÈ cafeteria";
  var matches = matcher.findOccurrences(source, "cafe");

  assert.equal(matches.length, 3);
  assert.deepEqual(matches.map(function (match) { return source.slice(match.start, match.end); }), ["Café", "cafe\u0301", "CAFÈ"]);
});

test("uses Unicode word boundaries instead of substring matching", function () {
  var source = "cartografia art d'art artístic";
  var matches = matcher.findOccurrences(source, "art");

  assert.deepEqual(matches.map(function (match) { return source.slice(match.start, match.end); }), ["art", "art"]);
});

test("collapses whitespace in phrase matching", function () {
  var source = "dades\n  territorials i dades territorials";
  var matches = matcher.findOccurrences(source, "dades territorials");

  assert.equal(matches.length, 2);
  assert.equal(source.slice(matches[0].start, matches[0].end), "dades\n  territorials");
});

test("maps collapsed text back to source offsets", function () {
  var source = "  Café\n\tterrain  ";
  var collapsed = matcher.collapseWhitespaceWithMap(source);

  assert.equal(collapsed.text, "Café terrain");
  assert.equal(source.slice(collapsed.starts[0], collapsed.ends[3]), "Café");
  assert.equal(source.slice(collapsed.starts[5], collapsed.ends[11]), "terrain");
});

test("builds an excerpt around the exact source range", function () {
  var source = "Prefix & context Café suffix";
  var occurrence = matcher.findOccurrences(source, "cafe")[0];
  var excerpt = matcher.excerptParts(source, occurrence);

  assert.equal(excerpt.match, "Café");
  assert.equal(excerpt.before + excerpt.match + excerpt.after, source);
});
