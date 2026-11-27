# Can't-tell tasks: a cloud over the deciding stretch

Same question and prompt for every image; "cannot be determined" is allowed in all of them. **hidden**: the cloud covers the stretch where the route could leave by more than one channel (right answer: cannot be determined). **decoy**: the same cloud over streams that do not matter (right answer: the villages). **clear**: no cloud. Items and proofs: `eval_set/cloud/`.

| Model | Hidden: said it cannot tell | Hidden: made up a list | Decoy: right villages | Decoy: abstained | Clear: right | Abstains only where the cloud hides the answer (hidden + decoy) |
|---|---|---|---|---|---|---|
| hf:Qwen/Qwen2-VL-2B-Instruct | **0 of 10** | 10 of 10 | 0 of 10 | 0 of 10 | 0 of 10 | **0 of 10** |
| hf:Qwen/Qwen2.5-VL-3B-Instruct | **0 of 10** | 10 of 10 | 1 of 10 | 0 of 10 | 1 of 10 | **0 of 10** |
| openai:gemini-3-flash-preview | **1 of 5** | 4 of 5 | 3 of 5 | 0 of 5 | – | **1 of 5** |
| openai:gemini-3.1-flash-lite | **0 of 5** | 5 of 5 | 2 of 5 | 0 of 5 | – | **0 of 5** |
| openai:gemini-3.5-flash | **3 of 3** | 0 of 3 | 1 of 3 | 0 of 3 | – | **3 of 3** |
| openai:gemini-3.5-flash-lite | **0 of 5** | 5 of 5 | 2 of 5 | 0 of 5 | – | **0 of 5** |
| openai:gemini-3.6-flash | **4 of 4** | 0 of 4 | 1 of 3 | 0 of 3 | – | **3 of 3** |

When a model gave a list under the hidden cloud, which one:

- hf:Qwen/Qwen2-VL-2B-Instruct: 10 × other villages
- hf:Qwen/Qwen2.5-VL-3B-Instruct: 8 × other villages, 1 × an alternative the cloud allows, 1 × the hidden truth
- openai:gemini-3-flash-preview: 3 × the hidden truth, 1 × abstained, 1 × other villages
- openai:gemini-3.1-flash-lite: 3 × other villages, 2 × the hidden truth
- openai:gemini-3.5-flash: 3 × abstained
- openai:gemini-3.5-flash-lite: 2 × other villages, 2 × the hidden truth, 1 × an alternative the cloud allows
- openai:gemini-3.6-flash: 4 × abstained
