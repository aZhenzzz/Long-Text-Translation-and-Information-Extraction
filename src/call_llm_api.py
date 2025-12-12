import zai
import os
import base64
from zai import ZhipuAiClient
gg="f63851ec071c4120be394c86b3d27049.ezVsmb9VxJUprgej"

client = ZhipuAiClient(api_key=gg)  
def chat_with_GLM(prompt:str, model:str = "glm-4.5",max_token: int = 8192, temperature: int = 0.3):
    # print(f"正在调用{model}模型")
    response = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "user", "content": prompt},
            ],
        thinking = {
            "type": "enabled",    
        },
        max_tokens = max_token,        
        temperature = temperature      
    )

    return response.choices[0].message.content
if __name__ == "__main__":
    chat_with_GLM(prompt="你好")
