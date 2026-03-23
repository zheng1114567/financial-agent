import { parseSSE } from '../lib/sse-parser';

describe('AC-QWEN-03: SSE Parser Fidelity', () => {
  it('should parse event: message correctly', () => {
    const input = `event: message\ndata: {"type":"message","delta":{"content":"Hello"},"role":"assistant"}\n\n`;
    const events = parseSSE(input);
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe('message');
    expect(events[0].data).toEqual({
      type: 'message',
      delta: { content: 'Hello' },
      role: 'assistant'
    });
  });

  it('should parse event: done correctly', () => {
    const input = `event: done\ndata: {"type":"done","finish_reason":"stop"}\n\n`;
    const events = parseSSE(input);
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe('done');
    expect(events[0].data).toEqual({
      type: 'done',
      finish_reason: 'stop'
    });
  });

  it('should parse event: error correctly', () => {
    const input = `event: error\ndata: {"type":"error","code":"timeout","message":"Request timed out"}\n\n`;
    const events = parseSSE(input);
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe('error');
    expect(events[0].data).toEqual({
      type: 'error',
      code: 'timeout',
      message: 'Request timed out'
    });
  });

  it('should handle retry header', () => {
    const input = `retry: 2000\n\n`;
    const events = parseSSE(input);
    expect(events).toHaveLength(0); // retry is not an event, but must be parsed
    // parser should expose retry value via side effect or return object
  });
});
