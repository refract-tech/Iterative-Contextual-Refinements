# Iterative Studio — Claude Code Fork

## Stato attuale

Fork di [ryoiki-tokuiten/Iterative-Contextual-Refinements](https://github.com/ryoiki-tokuiten/Iterative-Contextual-Refinements) con aggiunta del **ClaudeCodeProvider** — un provider che ruota le chiamate AI attraverso Claude Code CLI, usando i crediti del piano (Pro/Max) invece di API keys.

**Repo**: `github.com/refract-tech/Iterative-Contextual-Refinements`
**Upstream**: `github.com/ryoiki-tokuiten/Iterative-Contextual-Refinements`

## Cosa è stato fatto

### Commit 1: `feat: Claude Code provider`
- `Routing/ClaudeCodeProvider.ts` — Provider HTTP che parla col bridge
- `bridge_claude_code.py` — Server HTTP Python che riceve richieste e chiama `claude --print`
- `Routing/AIProvider.ts` — Aggiunto `claude-code` alla factory
- `Routing/ProviderManager.ts` — Registrato provider + modelli (opus/sonnet/haiku)

### Commit 2: `fix: stdin + UTF-8 + JSON fences`
- Prompt passato via stdin (`-p -`) invece che argomento CLI (limite Windows ~32K chars)
- Encoding UTF-8 forzato su subprocess (fix crash cp1252 su Windows)
- Strip automatico dei markdown code fences (````json...````) dalle risposte

### Commit 3: `fix: graceful connection handling`
- Catch `ConnectionAbortedError` quando il frontend timeout prima della risposta
- Timeout provider aumentato a 10 minuti

### Commit 4: `docs: complete setup guide`
- `CLAUDE_CODE_PROVIDER.md` — Documentazione completa con quick start, troubleshooting, architettura

## Cosa funziona

- **Deepthink mode**: ✅ Testato end-to-end con Haiku e Opus. Pipeline completa: Strategy Gen → Hypothesis Gen → Hypothesis Testing → Sub-Strategy → Red Team → Execution → Critique → Dissected Synthesis → Final Judge.
- **Contextual mode**: ✅ Dovrebbe funzionare (stesso `callAI()` path). Non testato esplicitamente.
- **Refine mode**: ✅ Dovrebbe funzionare. Non testato.
- **Export/Import**: ✅ Funziona. File `.msgpack.gz`. Bottone nella sidebar.

## Cosa NON funziona

- **Adaptive Deepthink**: ❌ Errore `Unsupported tool-calling provider: claude-code`. Richiede integrazione LangChain tool-calling (`LangGraphToolRuntime.ts`). Il nostro bridge fa solo testo → testo, non supporta il protocollo tool calling.
- **Agentic mode**: ❌ Stessa limitazione (usa LangGraph).
- **Auto-scroll UI**: Bug del progetto originale, non nostro. La pagina smette di scrollare automaticamente verso il basso dopo molti risultati.

## Come fixare Adaptive Deepthink (TODO)

File: `Core/LangGraphToolRuntime.ts` riga 112.

Il switch non ha un caso `claude-code`. Serve un custom `BaseChatModel` di LangChain che:
1. Riceve prompt + tool definitions
2. Chiama il bridge HTTP
3. Parsa i tool calls dalla risposta testuale di Claude
4. Ritorna nel formato `AIMessage` con `tool_calls` che LangChain si aspetta

Complessità: media-alta (~200-300 righe TypeScript + modifiche al bridge Python per gestire tool definitions nel prompt).

Alternativa più semplice: mappare `claude-code` al caso `anthropic` con una API key Anthropic reale. Ma questo usa crediti API, non plan credits.

## Architettura del provider

```
Browser (React/Vite)
  └── ClaudeCodeProvider.ts
        └── HTTP POST http://localhost:4141/generate
              └── bridge_claude_code.py
                    └── subprocess: claude --print --model {model} -p -
                          └── stdin: {system_prompt}\n---\n{user_prompt}
                    └── stdout → response JSON
              └── HTTP 200 { content: "..." }
  └── Risposta inserita nel pipeline Deepthink
```

## File chiave

| File | Descrizione |
|------|-------------|
| `Routing/ClaudeCodeProvider.ts` | Provider HTTP, timeout 10min, polling-free |
| `Routing/AIProvider.ts` | Factory con caso `claude-code` |
| `Routing/ProviderManager.ts` | Config provider + modelli default |
| `bridge_claude_code.py` | Server HTTP Python, auto-detect claude binary, UTF-8, fence stripping |
| `CLAUDE_CODE_PROVIDER.md` | Documentazione pubblica completa |
| `Core/LangGraphToolRuntime.ts` | Dove aggiungere supporto Adaptive Deepthink (TODO) |

## File del progetto originale da conoscere

| File | Descrizione |
|------|-------------|
| `Deepthink/DeepthinkCore.ts` | Pipeline Deepthink completa (~2136 righe) |
| `Deepthink/DeepthinkPrompts.ts` | Tutti i prompt template (~2246 righe) |
| `Deepthink/DeepthinkIterativeHistory.ts` | History managers per iterazioni |
| `Deepthink/SolutionPool.ts` | StructuredSolutionPool management |
| `Routing/AIService.ts` | Entry point per tutte le chiamate AI |
| `Core/State.ts` | Stato globale dell'app |
| `Core/ConfigManager.ts` | Export/import configurazione |
| `Core/App.ts` | Entry point dell'app, routing dei mode |
| `Contextual/ContextualCore.ts` | Pipeline Contextual (3 agenti) |
| `AdaptiveDeepthink/` | Pipeline Adaptive (tool calling, LangGraph) |
| `Agentic/` | Pipeline Agentic (tool calling, LangGraph) |

## Setup per sviluppo

```bash
cd "C:\Users\Edo\Desktop\Claude Code\Iterative-Contextual-Refinements"
npm install --legacy-peer-deps
npm run dev          # Terminal 1: frontend
python bridge_claude_code.py  # Terminal 2: bridge
```

## Regole

- **NON modificare i file core del progetto originale** (DeepthinkCore, DeepthinkPrompts, etc.) a meno che non sia strettamente necessario per l'integrazione
- **Ogni modifica va documentata** in questo file e nel CLAUDE_CODE_PROVIDER.md
- **Test prima di push**: verifica che Deepthink mode funzioni end-to-end
- **Commits puliti**: un commit per feature/fix, messaggio descrittivo

## Possibili miglioramenti futuri

1. **Adaptive Deepthink support** — custom LangChain BaseChatModel per tool calling via bridge
2. **Parallel request processing** — il bridge attualmente è sequenziale, potrebbe usare ThreadPoolExecutor
3. **Streaming responses** — il bridge potrebbe fare streaming della risposta claude via SSE
4. **Auto-scroll fix** — investigare il bug nella UI React originale
5. **Salvataggio automatico** — il bridge potrebbe salvare ogni risposta in un file markdown locale
6. **PR upstream** — se l'autore è interessato, proporre il provider come contributo
