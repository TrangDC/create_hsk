import vertexai
import os 

from vertexai.generative_models import GenerativeModel, Part, GenerationConfig

class VertexClient : 
    def __init__(self, project_id , creds , model ,  region="us-central1"):
        vertexai.init(
            project=project_id,
            location=region,
            credentials=creds
        )
        self.model = GenerativeModel(model)

    def send_data_to_AI(self, prompt ,data = None , mime_type = None ,temperature=0.5, top_p=0.8, response_mime_type=None, response_schema=None):
        parts = []
        if data and mime_type:
            parts.append(Part.from_data(data=data, mime_type=mime_type))
        parts.append(Part.from_text(prompt))
        
        # Thiết lập config hỗ trợ Structured Output
        config_args = {
            "temperature": temperature,
            "top_p": top_p
        }
        
        if response_mime_type:
            config_args["response_mime_type"] = response_mime_type
            
        if response_schema:
            config_args["response_schema"] = response_schema
            
        generation_config = GenerationConfig(**config_args)
        
        response = self.model.generate_content(parts, generation_config=generation_config)
        return response.text