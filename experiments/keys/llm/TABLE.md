# Key choice: the model alone and with ARRANGE's voice measurement (gold = the composer's 8 sighted keys on the canvas)

| who | condition | mean abs error (semitones) | within ±2 | octave errors (≥ 9 off) | unparsed |
|---|---|---|---|---|---|
| center.py (no model) | rule topnote | 4.1 | 2/8 | 0 | 0 |
| center.py (no model) | rule top | 2.9 | 3/8 | 0 | 0 |
| center.py (no model) | rule median | 2.1 | 5/8 | 0 | 0 |
| center.py (no model) | rule clip | 2.2 | 4/8 | 0 | 0 |
| claude-haiku-5-5 | name | 3.0 | 12/24 | 0 | 0 |
| claude-haiku-5-5 | numbers | 1.8 | 15/24 | 0 | 0 |
| claude-haiku-5-5 | anon | 1.8 | 15/24 | 0 | 0 |
| claude-haiku-5-5 | image | 2.0 | 16/24 | 0 | 0 |
| claude-opus-5-5 | name | 2.8 | 12/24 | 0 | 0 |
| claude-opus-5-5 | numbers | 1.7 | 17/24 | 0 | 0 |
| claude-opus-5-5 | anon | 1.7 | 18/24 | 0 | 0 |
| claude-opus-5-5 | image | 2.2 | 15/24 | 0 | 0 |
| claude-sonnet-5-5 | name | 2.4 | 12/24 | 0 | 0 |
| claude-sonnet-5-5 | numbers | 1.8 | 15/24 | 0 | 0 |
| claude-sonnet-5-5 | anon | 1.6 | 16/24 | 0 | 0 |
| claude-sonnet-5-5 | image | 2.0 | 17/24 | 0 | 0 |
| gemma-4-31b-fp8 | name | 3.9 | 8/24 | 1 | 0 |
| gemma-4-31b-fp8 | numbers | 2.5 | 12/24 | 0 | 0 |
| gemma-4-31b-fp8 | anon | 2.5 | 13/24 | 0 | 0 |
| gemma-4-31b-fp8 | image | 2.3 | 13/24 | 0 | 0 |
| qwen3.5-27b-fp8 | name | 2.9 | 11/24 | 0 | 0 |
| qwen3.5-27b-fp8 | numbers | 2.1 | 15/24 | 0 | 0 |
| qwen3.5-27b-fp8 | anon | 2.2 | 15/24 | 0 | 0 |
| qwen3.5-27b-fp8 | image | 3.1 | 10/24 | 1 | 1 |
