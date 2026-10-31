"""Image engine adapters — plug any generator behind one interface.

Order of preference for a commercial picture book:

| engine | why | license/cost |
|---|---|---|
| **ComfyUI** (local graph) | full control, LoRA stacking, reproducible seeds | open source, your GPU |
| **SDXL / Flux** via A1111/Forge API | mature, huge ecosystem, LoRA/ControlNet | open weights |
| **Replicate / Fal** | no GPU, pay per image, same open models | paid API |
| **OpenAI Images** | best text-free composition compliance | paid API |

Configure with env vars; nothing is called unless a provider is explicitly chosen.

    IMAGE_PROVIDER=a1111
    IMAGE_BASE_URL=http://127.0.0.1:7860
    IMAGE_MODEL=sdxl            # informational for a1111

    IMAGE_PROVIDER=replicate
    IMAGE_API_KEY=r8_...
    IMAGE_MODEL=stability-ai/sdxl

    IMAGE_PROVIDER=openai
    IMAGE_API_KEY=sk-...
    IMAGE_MODEL=gpt-image-1

    IMAGE_PROVIDER=huggingface
    HF_TOKEN=hf_...                       # never commit it
    IMAGE_MODEL=black-forest-labs/FLUX.1-schnell   # or stabilityai/stable-diffusion-xl-base-1.0

    IMAGE_PROVIDER=comfyui
    IMAGE_BASE_URL=http://127.0.0.1:8188
    IMAGE_WORKFLOW=secure_data/comfy_workflow.json
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests


@dataclass
class GenerationResult:
    path: str
    provider: str
    model: str
    width: int
    height: int
    seed: Optional[int]
    elapsed_s: float
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "provider": self.provider,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "elapsed_s": round(self.elapsed_s, 2),
            "meta": self.meta,
        }


class ImageEngineService:
    def __init__(self) -> None:
        self.provider = os.getenv("IMAGE_PROVIDER", "").strip().lower()
        self.base_url = os.getenv("IMAGE_BASE_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("IMAGE_API_KEY", "").strip() or os.getenv("HF_TOKEN", "").strip()
        self.model = os.getenv("IMAGE_MODEL", "").strip()
        self.workflow = os.getenv("IMAGE_WORKFLOW", "").strip()
        self.timeout = float(os.getenv("IMAGE_TIMEOUT", "600"))

    @property
    def available(self) -> bool:
        if self.provider == "a1111":
            return bool(self.base_url)
        if self.provider == "comfyui":
            return bool(self.base_url and self.workflow)
        if self.provider == "huggingface":
            return bool(self.api_key and self.model)
        if self.provider in ("replicate", "openai", "fal"):
            return bool(self.api_key)
        return False

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider or None,
            "model": self.model or None,
            "base_url": self.base_url or None,
            "has_api_key": bool(self.api_key),
            "workflow": self.workflow or None,
            "available": self.available,
            "hint": "Set IMAGE_PROVIDER (+ IMAGE_BASE_URL / IMAGE_API_KEY / IMAGE_MODEL). "
                    "Without it the pipeline still compiles prompts and layouts print placeholders.",
        }

    # ------------------------------------------------------------------ public
    def generate(
        self,
        prompt: Dict[str, Any],
        output_path: str,
        seed: Optional[int] = None,
        steps: int = 32,
        cfg_scale: float = 5.5,
    ) -> GenerationResult:
        if not self.available:
            raise RuntimeError(
                "No image provider configured (IMAGE_PROVIDER). "
                "Prompts can still be compiled and stored for a manual or offline run."
            )
        started = time.time()
        width = int(prompt.get("width_px", 1024))
        height = int(prompt.get("height_px", 1536))
        positive = str(prompt.get("positive", ""))
        negative = str(prompt.get("negative", ""))

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if self.provider == "a1111":
            data = self._a1111(positive, negative, width, height, steps, cfg_scale, seed)
        elif self.provider == "comfyui":
            data = self._comfyui(positive, negative, width, height, steps, cfg_scale, seed)
        elif self.provider == "replicate":
            data = self._replicate(positive, negative, width, height, steps, cfg_scale, seed)
        elif self.provider == "openai":
            data = self._openai(positive, width, height)
        elif self.provider == "fal":
            data = self._fal(positive, negative, width, height, steps, seed)
        elif self.provider == "huggingface":
            data = self._huggingface(positive, negative, width, height, steps, cfg_scale, seed)
        else:  # pragma: no cover
            raise RuntimeError(f"unsupported IMAGE_PROVIDER '{self.provider}'")

        output.write_bytes(data["bytes"])
        return GenerationResult(
            path=str(output),
            provider=self.provider,
            model=data.get("model", self.model),
            width=width,
            height=height,
            seed=data.get("seed", seed),
            elapsed_s=time.time() - started,
            meta=data.get("meta", {}),
        )

    # --------------------------------------------------------------- backends
    def _a1111(self, positive, negative, width, height, steps, cfg, seed) -> Dict[str, Any]:
        payload = {
            "prompt": positive,
            "negative_prompt": negative,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg,
            "sampler_name": os.getenv("IMAGE_SAMPLER", "DPM++ 2M Karras"),
            "seed": seed if seed is not None else -1,
        }
        response = requests.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        image = base64.b64decode(body["images"][0])
        info = json.loads(body.get("info", "{}")) if body.get("info") else {}
        return {"bytes": image, "seed": info.get("seed", seed), "meta": {"sampler": payload["sampler_name"]}}

    def _comfyui(self, positive, negative, width, height, steps, cfg, seed) -> Dict[str, Any]:
        """Minimal ComfyUI driver: your saved API workflow is patched with the prompt."""
        workflow = json.loads(Path(self.workflow).read_text(encoding="utf-8"))
        patched = json.loads(json.dumps(workflow))
        for node in patched.values():
            inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
            if "text" in inputs and isinstance(inputs["text"], str):
                if "negative" in str(node.get("class_type", "")).lower() or inputs["text"].startswith("NEG"):
                    inputs["text"] = negative
                else:
                    inputs["text"] = positive
            if "width" in inputs and isinstance(inputs["width"], int):
                inputs["width"] = width
            if "height" in inputs and isinstance(inputs["height"], int):
                inputs["height"] = height
            if "seed" in inputs and isinstance(inputs["seed"], (int, float)):
                inputs["seed"] = seed if seed is not None else inputs["seed"]
            if "steps" in inputs and isinstance(inputs["steps"], int):
                inputs["steps"] = steps
            if "cfg" in inputs and isinstance(inputs["cfg"], (int, float)):
                inputs["cfg"] = cfg

        queued = requests.post(f"{self.base_url}/prompt", json={"prompt": patched}, timeout=60)
        queued.raise_for_status()
        prompt_id = queued.json()["prompt_id"]

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            history = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30).json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node in outputs.values():
                    for image in node.get("images", []):
                        params = {
                            "filename": image["filename"],
                            "subfolder": image.get("subfolder", ""),
                            "type": image.get("type", "output"),
                        }
                        raw = requests.get(f"{self.base_url}/view", params=params, timeout=60)
                        raw.raise_for_status()
                        return {"bytes": raw.content, "seed": seed, "meta": {"prompt_id": prompt_id}}
                break
            time.sleep(2)
        raise TimeoutError("ComfyUI did not return an image before the timeout")

    def _replicate(self, positive, negative, width, height, steps, cfg, seed) -> Dict[str, Any]:
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"},
            json={
                "version": self.model,
                "input": {
                    "prompt": positive,
                    "negative_prompt": negative,
                    "width": width,
                    "height": height,
                    "num_inference_steps": steps,
                    "guidance_scale": cfg,
                    "seed": seed,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        prediction = response.json()
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            current = requests.get(
                prediction["urls"]["get"],
                headers={"Authorization": f"Token {self.api_key}"},
                timeout=30,
            ).json()
            if current["status"] == "succeeded":
                url = current["output"][0] if isinstance(current["output"], list) else current["output"]
                image = requests.get(url, timeout=120).content
                return {"bytes": image, "seed": seed, "meta": {"id": current.get("id")}}
            if current["status"] in ("failed", "canceled"):
                raise RuntimeError(f"replicate failed: {current.get('error')}")
            time.sleep(3)
        raise TimeoutError("replicate prediction timed out")

    def _fal(self, positive, negative, width, height, steps, seed) -> Dict[str, Any]:
        response = requests.post(
            f"https://fal.run/{self.model}",
            headers={"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"},
            json={
                "prompt": positive,
                "negative_prompt": negative,
                "image_size": {"width": width, "height": height},
                "num_inference_steps": steps,
                "seed": seed,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        url = body["images"][0]["url"]
        return {"bytes": requests.get(url, timeout=120).content, "seed": body.get("seed", seed), "meta": {}}

    def _huggingface(self, positive, negative, width, height, steps, cfg, seed) -> Dict[str, Any]:
        """Hugging Face Inference Providers (router first, legacy api-inference as fallback)."""
        payload = {
            "inputs": positive,
            "parameters": {
                "negative_prompt": negative,
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "guidance_scale": cfg,
                "seed": seed,
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "image/png"}
        urls = [
            f"https://router.huggingface.co/hf-inference/models/{self.model}",
            f"https://api-inference.huggingface.co/models/{self.model}",
        ]
        last_error = None
        for url in urls:
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                content_type = response.headers.get("content-type", "")
                if response.status_code == 200 and not content_type.startswith("application/json"):
                    return {"bytes": response.content, "seed": seed,
                            "meta": {"endpoint": url.split("/models/")[0], "model": self.model}}
                if response.status_code in (401, 403):
                    raise RuntimeError("Hugging Face rejected the token (check HF_TOKEN and model access)")
                last_error = f"{response.status_code}: {response.text[:200]}"
            except Exception as exc:  # try the next endpoint
                last_error = str(exc)
        raise RuntimeError(f"huggingface image generation failed ({last_error})")

    def _openai(self, positive, width, height) -> Dict[str, Any]:
        size = self._openai_size(width, height)
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model or "gpt-image-1", "prompt": positive, "size": size, "n": 1},
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        item = body["data"][0]
        if item.get("b64_json"):
            payload = base64.b64decode(item["b64_json"])
        else:
            payload = requests.get(item["url"], timeout=120).content
        return {"bytes": payload, "seed": None, "meta": {"size": size}}

    @staticmethod
    def _openai_size(width: int, height: int) -> str:
        ratio = width / max(1, height)
        if ratio < 0.85:
            return "1024x1536"
        if ratio > 1.15:
            return "1536x1024"
        return "1024x1024"
