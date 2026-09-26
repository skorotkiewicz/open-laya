For a clean-download

Use an explicit persistent cache and download before starting the server:

 ```sh
export HF_HOME="$HOME/laya/hf-cache"

.venv/bin/hf download \
    convaiinnovations/laya \
    --revision 55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851 \
    --include 'typed-decisions/*'
 ```

Then start with the same HF_HOME:

 ```sh
HF_HOME="$HOME/laya/hf-cache" \
LAYA_API_KEY=1111 \
.venv/bin/python server.py
 ```

Once cached, production can prevent network access:

```sh
HF_HUB_OFFLINE=1 \
HF_HOME="$HOME/laya/hf-cache" \
LAYA_API_KEY=1111 \
.venv/bin/python server.py
```

To download specific checkpoints:

```sh
# Multilingual only
hf download convaiinnovations/laya \
  --revision 55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851 \
  --include 'multilingual/*'

# Typed decisions and multilingual
hf download convaiinnovations/laya \
  --revision 55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851 \
  --include 'typed-decisions/*' 'multilingual/*'
```

To cache the entire repository, omit --include:

```sh
hf download convaiinnovations/laya \
  --revision 55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851
```
