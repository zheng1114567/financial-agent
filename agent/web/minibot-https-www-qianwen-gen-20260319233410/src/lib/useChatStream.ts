import { useState, useEffect, useCallback } from 'react';
import { apiJsonHeaders } from './api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface StreamEvent {
  event: 'message' | 'done' | 'error';
  data: any;
}

export const useChatStream = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const streamChat = useCallback(async (input: string, model: string = 'qwen-plus') => {
    if (!input.trim()) return;

    setIsLoading(true);
    setError(null);
    const newMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, newMessage]);

    try {
      const response = await fetch('/api/v2/chat', {
        method: 'POST',
        headers: apiJsonHeaders(),
        body: JSON.stringify({
          messages: [{ role: 'user', content: input }],
          model,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (response.headers.get('content-type') !== 'text/event-stream') {
        throw new Error('Expected text/event-stream response');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('ReadableStream not supported');

      let accumulatedContent = '';
      const botMessage: Message = { role: 'assistant', content: '' };
      setMessages(prev => [...prev, botMessage]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = new TextDecoder().decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('event: message')) {
            // next line is data: {...}
            continue;
          }
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.delta?.content) {
                accumulatedContent += data.delta.content;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].content = accumulatedContent;
                  return newMsgs;
                });
              }
              if (data.finish_reason === 'stop') {
                break;
              }
            } catch (e) {
              console.warn('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setMessages(prev => prev.slice(0, -1)); // remove pending bot msg
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { messages, isLoading, error, streamChat };
};