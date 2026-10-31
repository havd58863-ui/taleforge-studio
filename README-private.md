# TaleForge Studio — Private Commercial Repository

This repository is intended for private commercial development only.

## Protected content
- story ideas and original concepts
- world-building and character sheets
- prompts and prompt recipes
- LoRA files, references and datasets (`secure_data/`)
- generated outputs and print-ready files (`output/`)
- metadata, public listing copy, pricing strategy

## Security notes
- Use GitHub Secrets for all tokens (`SECRET_KEY`, `KAGGLE_*`, `DATABASE_URL`)
- Use `.env` locally only — it is git-ignored
- Never commit `kaggle.json`, GitHub tokens or API keys
- Keep sensitive assets under `secure_data/` (git-ignored except its README files)
- Do not publish proprietary content or generated interiors
- Rotate any key that has ever appeared in a chat, screenshot or commit
