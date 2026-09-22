// Forwards raw mic PCM (channel 0) to the page unmodified (docs/adr/ADR-0004).
// MediaRecorder isn't used: lossy codecs alter reverberant tails and the
// modulation spectrum SRMR measures.
class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) this.port.postMessage(ch.slice(0));
    return true;
  }
}
registerProcessor('recorder', RecorderProcessor);
