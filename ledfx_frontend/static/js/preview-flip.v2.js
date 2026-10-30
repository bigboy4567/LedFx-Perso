/*
 * Local addition to the LedFx frontend: show the live previews mirrored, for
 * strips whose first LED is on the right-hand end. One switch for every preview;
 * only the picture in the browser turns round, the LEDs are left alone.
 *
 * The bundle calls ledfxPreview.pixels() on every visualisation update, and the
 * ⇄ button next to the pause button calls ledfxPreview.toggle().
 */
(function () {
  "use strict";
  var KEY = "ledfx-flip-previews";
  // The first version flipped strips one by one: any strip flipped there turns this on
  var OLD_KEY = "ledfx-flipped-previews";
  var flipped = false;
  try {
    var saved = window.localStorage.getItem(KEY);
    if (saved === null) {
      flipped = JSON.parse(window.localStorage.getItem(OLD_KEY) || "[]").length > 0;
    } else {
      flipped = saved === "1";
    }
    window.localStorage.removeItem(OLD_KEY);
  } catch (error) {
    flipped = false;
  }

  // Reverses each row of a flat list of items, so a matrix flips left to right
  function flipRows(list, columns, size) {
    var out = new list.constructor(list.length);
    var rowLength = columns * size;
    for (var start = 0; start < list.length; start += rowLength) {
      var end = Math.min(start + rowLength, list.length);
      var count = (end - start) / size;
      for (var i = 0; i < count; i++) {
        for (var k = 0; k < size; k++) {
          out[start + i * size + k] = list[end - (i + 1) * size + k];
        }
      }
    }
    return out;
  }

  window.ledfxPreview = {
    isFlipped: function () {
      return flipped;
    },
    toggle: function () {
      flipped = !flipped;
      try {
        window.localStorage.setItem(KEY, flipped ? "1" : "0");
      } catch (error) {
        // Private browsing: the choice lasts until the page closes
      }
      window.dispatchEvent(new Event("ledfx-preview-flip"));
      return flipped;
    },
    pixels: function (event) {
      var pixels = event.pixels;
      if (!pixels || !flipped) return pixels;
      var shape = event.shape || [];
      if (typeof pixels === "string") {
        // Compressed mode: base64 of the RGB bytes, row after row
        var binary = window.atob(pixels);
        var bytes = new Uint8Array(binary.length);
        for (var b = 0; b < binary.length; b++) bytes[b] = binary.charCodeAt(b);
        var columns = shape[1] || bytes.length / 3;
        var turned = flipRows(bytes, columns, 3);
        var text = "";
        for (var c = 0; c < turned.length; c += 0x8000) {
          text += String.fromCharCode.apply(null, turned.subarray(c, c + 0x8000));
        }
        return window.btoa(text);
      }
      // Plain mode: one list per color channel
      return pixels.map(function (channel) {
        return Array.from(flipRows(channel, shape[1] || channel.length, 1));
      });
    },
  };
})();
