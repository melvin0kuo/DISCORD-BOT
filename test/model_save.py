from transformers import AutoProcessor, AutoModelForImageTextToText

# 載入模型和分詞器
model_name = "mistralai/Mistral-Small-3.1-24B-Instruct-2503"
model = AutoProcessor.from_pretrained(model_name)
tokenizer = AutoModelForImageTextToText.from_pretrained(model_name)

# 保存到本地目錄
output_dir = r"C:\Users\harekaze\Documents\Project-self\Discord\models"
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
