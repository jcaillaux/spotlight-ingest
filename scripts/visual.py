from config import IMG
from transformers import AutoImageProcessor, AutoModel
from PIL import Image
import torch

def main():
    imgs = list(IMG.glob('*'))
    processor = AutoImageProcessor.from_pretrained('facebook/dinov2-small')
    model = AutoModel.from_pretrained('facebook/dinov2-small')

    for i, img in enumerate(imgs) :

        print(f"\r{100*(i+1)/len(imgs):.2f}%", end="\033[0m", flush=True)

        image = Image.open(img)
        with torch.no_grad():
            inputs = processor(images=image, return_tensors="pt")
            outputs = model(**inputs)
            cls = outputs.pooler_output
    print()

    

if __name__ == '__main__':
    main()