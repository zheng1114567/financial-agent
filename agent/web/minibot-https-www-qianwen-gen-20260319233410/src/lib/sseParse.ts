/**
 * 增量解析 SSE（後端為 event: + 換行 + data: 格式，chunk 可能切在半行）
 */
export type SSEvent = { event: string; data: string };

export function createSSEParser(onEvent: (ev: SSEvent) => void) {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk;
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const raw of blocks) {
      const block = raw.trim();
      if (!block) continue;
      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        const t = line.trim();
        if (!t) continue;
        if (t.startsWith("event:")) eventName = t.slice(6).trim();
        else if (t.startsWith("data:")) dataLines.push(t.slice(5).trim());
      }
      onEvent({ event: eventName, data: dataLines.join("\n") });
    }
  };
}

export function parseSSEDataJson(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}
