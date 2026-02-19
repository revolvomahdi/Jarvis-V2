import torch
from diffusers import StableDiffusionPipeline
import os
from datetime import datetime
import threading

class ImageGenerator:
    def __init__(self):
        self.output_dir = "web/static/generated_images"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        self.pipeline = None
        self.model_id = "Lykon/dreamshaper-8"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.is_ready = False
        
        # Start loading in background
        threading.Thread(target=self._load_pipeline, daemon=True).start()

    def _load_pipeline(self):
        try:
            print(f"[INFO] Sanat Departmani: '{self.model_id}' Modelini Yukluyor...")
            
            # Device check
            if torch.cuda.is_available():
                self.device = "cuda"
                dtype = torch.float16
                variant = "fp16"
                print("[INFO] GPU (CUDA) Tespit Edildi. Yuksek Performans Modu Aktif.")
            else:
                self.device = "cpu"
                dtype = torch.float32
                variant = None
                print("[WARN] GPU Bulunamadi. CPU Moduna Geciliyor (Yavas olabilir).")

            # Load Pipeline
            self.pipeline = StableDiffusionPipeline.from_pretrained(
                self.model_id, 
                torch_dtype=dtype,
                variant=variant,
                use_safetensors=True
            )
            
            # Optimizations
            if self.device == "cuda":
                self.pipeline.to("cuda")
                # enable_model_cpu_offload requires 'accelerate'
                try:
                    self.pipeline.enable_model_cpu_offload()
                    print("[INFO] VRAM Optimizasyonu (CPU Offload) Aktif.")
                except ImportError:
                    print("[WARN] 'accelerate' kutuphanesi eksik, standart VRAM yonetimi kullaniliyor.")
                
                self.pipeline.enable_vae_slicing()
            else:
                self.pipeline.to("cpu")
                
            self.is_ready = True
            print(f"[SUCCESS] Sanat Departmani: Cizim yapmaya hazir!")
            
        except Exception as e:
            print(f"[ERROR] Sanat Departmani Hatasi: {e}")
            import traceback
            traceback.print_exc()

    def generate(self, prompt, progress_callback=None):
        if not self.is_ready:
            return None 

        try:
            print(f"[INFO] Sanat Departmani Ciziyor: {prompt}")
            
            # Progress Wrapper
            steps = 20
            
            def callback_fn(step, timestep, latents):
                if progress_callback:
                    # step is tensor or int depending on diffusers version
                    progress = int((step + 1) / steps * 100)
                    progress = min(99, max(20, progress)) # Map to 20-99% range
                    progress_callback(progress, f"Çiziliyor... %{progress}")

            # Note: diffusers callback happens AFTER step, so step 0 is done.
            image = self.pipeline(
                prompt, 
                num_inference_steps=steps, 
                guidance_scale=7.5,
                callback=callback_fn,
                callback_steps=1
            ).images[0]
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gen_{timestamp}.jpg"
            path = os.path.join(self.output_dir, filename)
            image.save(path)
            
            if progress_callback: progress_callback(100, "Tamamlandı!")
            return f"/static/generated_images/{filename}"
            
        except Exception as e:
            print(f"[ERROR] Generation Error: {e}")
            return None
