# Bangla AI IME

Ubuntu (IBus) er jonno Bangla input method. Banglish e type korben, Bangla pabe. Shathe Claude
context bujhe smart suggestion dibe, code editor er IntelliSense/Copilot er moto.

## Kivabe kaj kore

```
keystroke ──► IBus engine (bangla_ai/engine.py)
               ├─ Local layer (instant, offline)
               │    apnar shekha word + 34k shobder dictionary + Avro-style rule → popup
               └─ Claude layer (typing e ~300ms pause hole)
                    context + current word → Claude API
                    → popup e ✦ word, inline completion (Tab = accept)
```

- **Dictionary:** `bhalo` → ভালো, `porikkha` → পরীক্ষা, `dhonnobad` → ধন্যবাদ, `shami` → স্বামী.
  ত/ট, স/শ/ষ, ই/ঈ, ন/ণ, য-ফলা, ব-ফলা na mille o thik banan ta khuje dey, shobcheye
  common ta age. Capital diye likhle (`Tak` → টাক) oita age ashe. Adha word e
  (`bangl` → বাংলা, বাংলাদেশ) completion o dey.
- **AI auto-select:** Claude er answer ashle se nijei bujhe ney apni kon Bangla shobdo likhte
  chacchen, ar sheta select kore dey: `hello` → হ্যালো, `phone` → ফোন. ↑↓ diye bodlano jay.
  Ager bar ei letter gulo diye je shobdo bechhe niyechen, sheta i select thake.
- **Popup:** local candidate prothome thake (Space dile oita bose), tarpor Claude er ✦ word,
  tarpor onno variant.
- **Inline completion:** Claude er porer kotha cursor er pore underline/gray hoye dekhay.
  Tab = accept, Esc = bad, type korte thakle nije chole jay.
- **Shekha:** apni je word select koren, porer bar oi Banglish er jonno sheta age ashe.

## Install

Ubuntu (GNOME, IBus) te test kora. Python 3.10 ba notun lagbe.

```bash
git clone https://github.com/hasibul-hossain1/Bangla-Ai-keyboard.git
cd Bangla-Ai-keyboard
./install.sh                 # apt packages + venv + IBus component (sudo lagbe)
bangla-ai-ime --set-key      # Anthropic API key (GNOME Keyring e save hoy)
```

Tarpor: **Settings → Keyboard → Input Sources → + → Bangla → "Bangla AI (Phonetic + Claude)"**.
`Super+Space` diye English ↔ Bangla AI switch korun. (Input source ekta thakle `Super+Space` kichu kore na.)

Terminal theke add korte chaile:

```bash
gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'us'), ('ibus', 'bangla-ai')]"
```

Install charai shudhu phonetic rule dekhte: `python3 -m bangla_ai --show ami bhalo korbo`

## Key gulo

| Key | Kaj |
|---|---|
| a-z, A-Z | Banglish letter, popup update hoy |
| Space | selected word + space commit |
| 1-9 / mouse click | oi number er candidate commit |
| ↑ ↓ / PgUp PgDn | popup e select bodlano |
| Tab | inline completion accept (dekhale) |
| Esc | completion bad; composing obosthay Latin letter jemon ache temon commit (English word er jonno) |
| Backspace | shesh letter muche |
| `.` | `।` (number er pore `.` i thake) |
| Enter, Tab, arrow | word commit kore key ta app ke dey |

### Phonetic niyom (Avro style)

- Consonant er pore vowel = kar: `ami` → আমি, `kemon` → কেমন
- Consonant er pore `o` = kichu na (inherent): `bhalo` → ভাল (popup e ভালো o thake)
- Duita consonant pashapashi = juktakkhor: `onno` → অন্ন. Bhangte `` ` `` din: `` k`k `` → কক
- Case sensitive: `t` ত / `T` ট, `d` দ / `D` ড, `n` ন / `N` ণ, `s` স / `S` শ / `Sh` ষ,
  `r` র / `R` ড়, `y` য় / `Z` য-ফলা, `O` ো, `I` ী, `U` ূ, `OI` ৈ, `OU` ৌ
- `ng` ং, `Ng` ঙ, `^` ঁ, `:` ঃ (`du:kho` → দুঃখ), ``` t`` ``` ৎ, `rri` ৃ

## Settings

`~/.config/bangla-ai-ime/config.json` (prothom run e toiri hoy). Bodlanor por `ibus restart`.

| Key | Default | Mane |
|---|---|---|
| `model` | `claude-haiku-5-5` | Claude model. Haiku shobcheye druto. Aro bhalo suggestion chaile `claude-sonnet-5-5` ba `claude-opus-5-5` (dhire) |
| `effort` | `low` | Claude koto bhabbe. Kom = druto |
| `claude_enabled` | `true` | Claude e kichu pathabe kina (input menu theke o toggle kora jay) |
| `inline_completion` | `true` | Inline completion (menu theke o toggle) |
| `auto_select_claude` | `true` | Claude er best guess nije select hoy, Space e sheta bose. ↑↓ diye onno ta neya jay. Ager bar ei letter e je word bechhe nichhen, sheta select thake |
| `debounce_ms` | `300` | Shesh key er koto ms por Claude ke jiggesh korbe |
| `context_chars` | `120` | Ager koto character context hishebe jabe |
| `min_prediction_words` | `1` | Koyta word type korar por next-word prediction shuru hobe |
| `max_claude_words` | `4` | Popup e Claude er koyta word |
| `request_timeout_seconds` | `8.0` | Claude request timeout |
| `bangla_digits` | `false` | 0-9 → ০-৯ |
| `dari_for_period` | `true` | `.` → `।` |

Purono install e `config.json` e ager model (`claude-opus-5-5`) save kora thakte pare. Haiku chaile
oikhane `"model": "claude-haiku-5-5"` kore `ibus restart` din.

Ek shomoy ekta request i Claude e jay. Type korte thakle opekkhay thaka purono request bad pore jay,
shudhu shesh ta jay. Ekoi shesh 3 word er pore ekoi word hole cache theke sathe sathe answer ashe.

Model `claude-opus-5-5`, `claude-opus-5`, `claude-sonnet-5-5` ba `claude-fable-5-1` hole server-side
refusal fallback (`fallbacks: "default"`) on thake.

## Privacy

- Claude on thakle ja type koren (shesh `context_chars` character + current word) Anthropic API te jay.
- Password/PIN field e engine puro bondho thake, kichui pathay na.
- Top bar er keyboard menu theke "Claude suggestion" off korle shudhu local layer chole.
- API key GNOME Keyring e thake. Keyring na pele `~/.config/bangla-ai-ime/api_key` (chmod 600).
- Log e typed text ba key kokhono lekha hoy na: `~/.cache/bangla-ai-ime/engine.log`.

## Shimabaddhota

- Inline completion er gray rong app er upor nirbhor kore. Onek app shudhu underline dekhay.
- IME shudhu ei field e apnar type kora text dekhe. Mouse e cursor shorale context reset hoy.
- Chrome/Electron app (VS Code, Slack) e Wayland IME er jonno `--enable-wayland-ime` flag lagte pare.

## Test

```bash
# install er por (Claude test er jonno anthropic SDK lage, oita venv e ache)
~/.local/lib/bangla-ai-ime/venv/bin/python -m unittest discover -s tests -t .
# install charai: Claude test gulo skip hobe
python3 -m unittest discover -s tests -t .
```

**Status (2026-11-19, Ubuntu 26.04 GNOME Wayland, IBus 1.5.34):**

- 28/28 unit test pass (phonetic, user dictionary, Claude layer fake HTTP diye).
- 2026-11-23: dictionary, Claude request queue ar AI auto-select jog hoyeche. 40/40 unit test pass
  (installed venv e, real SDK diye).
- Engine smoke test: real IBus connection e simulated key diye 41/41 check pass.
- `./install.sh` kaj kore, IBus engine ta list e ashe.
- Ekhono baki: GNOME app e lomba shomoy ashol typing, ashol Claude API call.

## Dictionary

`bangla_ai/data/words.txt` asheche [FrequencyWords](https://github.com/hermitdave/FrequencyWords)
(OpenSubtitles 2018, Hermit Dave, CC BY-SA 4.0) theke, `tools/build_dict.py` diye filter kora.
Notun list diye abar banate:

```bash
python3 tools/build_dict.py bn_full.txt bangla_ai/data/words.txt
```

## Uninstall

```bash
./uninstall.sh
```
