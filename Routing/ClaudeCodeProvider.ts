/**
 * ClaudeCodeProvider — Routes AI calls through Claude Code subagents.
 *
 * Uses HTTP to communicate with bridge_claude_code.py running locally.
 * The bridge receives requests, runs Claude Code CLI, returns responses.
 *
 * This allows using Claude Code plan credits instead of API keys.
 * Zero cost, full agentic isolation per call.
 *
 * @license Apache-2.0
 */

import { AIProvider, StructuredMessage } from './AIProvider';
import { GenerateContentResponse, Part } from "@google/genai";

const BRIDGE_URL = 'http://localhost:4141';
const TIMEOUT_MS = 300000; // 5 minutes per call

function isStructuredMessages(input: any): input is StructuredMessage[] {
    return Array.isArray(input) && input.length > 0 && 'role' in input[0] && 'content' in input[0];
}

export class ClaudeCodeProvider implements AIProvider {
    private initialized: boolean = false;

    initialize(apiKey: string): boolean {
        // No API key needed — we use Claude Code plan credits
        // Just mark as initialized; the bridge health check happens on first call
        this.initialized = true;
        console.log('🔗 ClaudeCodeProvider initialized (HTTP bridge at ' + BRIDGE_URL + ')');
        return true;
    }

    async generateContent(
        promptOrParts: string | Part[] | StructuredMessage[],
        temperature: number,
        modelToUse: string,
        systemInstruction?: string,
        isJsonOutput: boolean = false,
        topP?: number,
        thinkingConfig?: any
    ): Promise<GenerateContentResponse> {
        if (!this.initialized) throw new Error("ClaudeCodeProvider not initialized.");

        // Build the prompt text from various input formats
        let userPrompt: string;
        let conversationHistory: { role: string; content: string }[] = [];

        if (isStructuredMessages(promptOrParts)) {
            for (const msg of promptOrParts) {
                conversationHistory.push({
                    role: msg.role,
                    content: msg.content
                });
            }
            const lastUser = conversationHistory.filter(m => m.role === 'user').pop();
            userPrompt = lastUser?.content || '';
        } else if (typeof promptOrParts === 'string') {
            userPrompt = promptOrParts;
        } else {
            userPrompt = (promptOrParts as any[])
                .filter((p: any) => p.text)
                .map((p: any) => p.text)
                .join('\n');
        }

        const request = {
            id: `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            system_prompt: systemInstruction || '',
            user_prompt: userPrompt,
            conversation_history: conversationHistory.length > 0 ? conversationHistory : undefined,
            temperature,
            model: modelToUse,
            json_output: isJsonOutput,
        };

        console.log(`📤 ClaudeCode request ${request.id} → bridge...`);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

        try {
            const resp = await fetch(`${BRIDGE_URL}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request),
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!resp.ok) {
                const errText = await resp.text();
                throw new Error(`Bridge error (${resp.status}): ${errText}`);
            }

            const data = await resp.json();
            const content = data.content || data.text || '';

            console.log(`📥 ClaudeCode response (${content.length} chars)`);

            const mockResponse = {
                text: content,
                response: {
                    text: () => content,
                    candidates: [{
                        content: {
                            parts: [{ text: content }]
                        }
                    }]
                }
            };

            return mockResponse as any;

        } catch (e: any) {
            clearTimeout(timeoutId);
            if (e.name === 'AbortError') {
                throw new Error(`ClaudeCodeProvider: Timeout (${TIMEOUT_MS / 1000}s). Is bridge_claude_code.py running?`);
            }
            throw new Error(`ClaudeCodeProvider: ${e.message}. Is bridge_claude_code.py running on ${BRIDGE_URL}?`);
        }
    }

    isInitialized(): boolean {
        return this.initialized;
    }

    getProviderName(): string {
        return 'claude-code';
    }
}
