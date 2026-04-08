/**
 * ClaudeCodeProvider — Routes AI calls through Claude Code subagents.
 *
 * Uses file-based IPC: writes requests to .claude_request.json,
 * a bridge script (bridge_claude_code.py) picks them up, runs a
 * Claude Code subagent, and writes the response to .claude_response.json.
 *
 * This allows using Claude Code plan credits instead of API keys.
 * Zero cost, full agentic isolation per call.
 *
 * @license Apache-2.0
 */

import { AIProvider, StructuredMessage } from './AIProvider';
import { GenerateContentResponse, Part } from "@google/genai";
import * as fs from 'fs';
import * as path from 'path';

// IPC directory — requests and responses are exchanged here
const IPC_DIR = path.resolve(__dirname, '..', '.claude_ipc');
const REQUEST_FILE = path.join(IPC_DIR, 'request.json');
const RESPONSE_FILE = path.join(IPC_DIR, 'response.json');
const LOCK_FILE = path.join(IPC_DIR, 'request.lock');

// Polling interval and timeout
const POLL_INTERVAL_MS = 500;
const TIMEOUT_MS = 300000; // 5 minutes per call

function isStructuredMessages(input: any): input is StructuredMessage[] {
    return Array.isArray(input) && input.length > 0 && 'role' in input[0] && 'content' in input[0];
}

function ensureIpcDir(): void {
    if (!fs.existsSync(IPC_DIR)) {
        fs.mkdirSync(IPC_DIR, { recursive: true });
    }
}

function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export class ClaudeCodeProvider implements AIProvider {
    private initialized: boolean = false;

    initialize(apiKey: string): boolean {
        // No API key needed — we use Claude Code plan credits
        ensureIpcDir();
        this.initialized = true;
        console.log('🔗 ClaudeCodeProvider initialized (file-based IPC)');
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

        ensureIpcDir();

        // Build the prompt text from various input formats
        let userPrompt: string;
        let conversationHistory: { role: string; content: string }[] = [];

        if (isStructuredMessages(promptOrParts)) {
            // Multi-turn conversation
            for (const msg of promptOrParts) {
                conversationHistory.push({
                    role: msg.role,
                    content: msg.content
                });
            }
            // Use the last user message as the main prompt
            const lastUser = conversationHistory.filter(m => m.role === 'user').pop();
            userPrompt = lastUser?.content || '';
        } else if (typeof promptOrParts === 'string') {
            userPrompt = promptOrParts;
        } else {
            // Part[] — extract text parts
            userPrompt = (promptOrParts as Part[])
                .filter((p: any) => p.text)
                .map((p: any) => p.text)
                .join('\n');
        }

        // Build the request payload
        const request = {
            id: `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            system_prompt: systemInstruction || '',
            user_prompt: userPrompt,
            conversation_history: conversationHistory.length > 0 ? conversationHistory : undefined,
            temperature,
            model: modelToUse,
            json_output: isJsonOutput,
            timestamp: new Date().toISOString(),
        };

        // Clean up any stale response file
        if (fs.existsSync(RESPONSE_FILE)) {
            fs.unlinkSync(RESPONSE_FILE);
        }

        // Write request
        fs.writeFileSync(REQUEST_FILE, JSON.stringify(request, null, 2), 'utf-8');

        // Signal the bridge that a request is ready
        fs.writeFileSync(LOCK_FILE, request.id, 'utf-8');

        console.log(`📤 ClaudeCode request ${request.id} written, waiting for bridge...`);

        // Poll for response
        const startTime = Date.now();
        while (Date.now() - startTime < TIMEOUT_MS) {
            if (fs.existsSync(RESPONSE_FILE)) {
                try {
                    const responseRaw = fs.readFileSync(RESPONSE_FILE, 'utf-8');
                    const response = JSON.parse(responseRaw);

                    // Clean up
                    fs.unlinkSync(RESPONSE_FILE);
                    if (fs.existsSync(LOCK_FILE)) fs.unlinkSync(LOCK_FILE);
                    if (fs.existsSync(REQUEST_FILE)) fs.unlinkSync(REQUEST_FILE);

                    const content = response.content || response.text || '';
                    console.log(`📥 ClaudeCode response received (${content.length} chars)`);

                    // Convert to Gemini-like format for compatibility
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
                } catch (e) {
                    // Response file exists but is not valid JSON yet — bridge still writing
                    await sleep(POLL_INTERVAL_MS);
                    continue;
                }
            }
            await sleep(POLL_INTERVAL_MS);
        }

        // Timeout
        if (fs.existsSync(LOCK_FILE)) fs.unlinkSync(LOCK_FILE);
        if (fs.existsSync(REQUEST_FILE)) fs.unlinkSync(REQUEST_FILE);
        throw new Error(`ClaudeCodeProvider: Timeout waiting for response (${TIMEOUT_MS / 1000}s). Is bridge_claude_code.py running?`);
    }

    isInitialized(): boolean {
        return this.initialized;
    }

    getProviderName(): string {
        return 'claude-code';
    }
}
