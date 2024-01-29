#WARNING: Use it only for reference don't use it in production!
"""If you want to create separete sapce for each user via login u can refer this code."""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import generics
import csv
import json
import sys
import openai
import os
from dotenv import load_dotenv
import requests

from . import prompts as pr
from .models import Fields, End_points, Users


load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

def api_caller(api_address, payload):
            
    api_address = api_address.replace("POST api/Player/", "")
    url = "https://api20.futalert.co.uk/api/player/" + api_address.replace(".", "")
    payload = payload
    try:
        overall = payload['Overall']
        if overall == "":
            payload.pop('Overall')
        
    except:
        overall = payload.get('Overall')
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print("Futt API Response:", data, "---------------------------------")
        return ({"success": data, "payload": payload})
    
    else:
        return ({"failiure": "Issues in processing you request please try again later or try another questions.","payload":payload})

def json_formatter(api_address, question):
    
    #Header of the prompt
    prompt = """You are a JSON generator. Your task is to generate JSON from user question. Generate JSON as mentioned in the Fields.Don't use the word 'JSON' in any of your output instead of that use the word 'response'.
Fields:
"""
    #Generating body of the prompt 
    fields = Fields.objects.filter(api_address = api_address)

    for field in fields:
        check = 0
        line = f"{field.field_name}: {field.field_type} field. "
        description = field.description if field.description.endswith('.') else field.description + '. '
        if field.required:
            ask = "*required. If not specified in question, before generating JSON get the value from user and then generate JSON."
        elif field.default_value:
            ask = f"If not specified in the question, use {field.default_value} as default value."
        elif not field.default_value:
            ask = "It is optional field if not specified in question no need to add this field in JSON."
        else:
            ask = ""
        
        if field.csv_file:
            csv_file = Fields.objects.get(pk=field.id)
            file_content = csv_file.csv_file.read().decode('utf-8').splitlines()

            # Assuming CSV has a header, skip the header row
            csv_data = list(csv.DictReader(file_content, delimiter=','))

            formatted_output = ""
            # Construct the string with desired formatting
            formatted_output += '\t'.join(csv_data[0].keys()) + '\n'  # Header row
            for row in csv_data:
                formatted_output += '\t'.join(row.values()) + '\n'
            check = 1

        line = line + description + ask
        if check == 1:
            line = line + "\n \t To map use this table: \n" + formatted_output
        prompt = prompt + line + "\n"

    #Footer of the prompt
    end_msg = f"""Don't forget that you should not use the word 'JSON' in any of our response.""" 

    prompt = prompt + end_msg

    #returning final prompt
    print("prompt:", prompt, "-----------------------------------------------------------------------")
    return(prompt)



def get_api_address(question):
    end_point = list(End_points.objects.values_list('api_address', flat=True))
    description = list(End_points.objects.values_list('description', flat=True))

    context = ""
    for i in range(0, len(end_point)):
        context = context + end_point[i]+". "
        context = context + description[i]  + "\n"

    #To generate prompt
    prompt = pr.API_FINDER.format(api_list = context, question = question)
    
    #Calling ai and get appropriate API for the given question
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    api_address = completion.choices[0].message.content

    return api_address


def get_formated_json(api_address, question, user):

    api_address_id =  End_points.objects.get(api_address = api_address)

    if not user.cleared:

        conversation = user.need_history
        completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            messages = conversation,
            temperature = 0.7,
            top_p = 1.0,
        )

    else:
        prompt = json_formatter(api_address_id.id, question)
        conversation = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": question}
        ]
        completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            messages = conversation,
            temperature = 0.7,
            top_p = 1.0,
        )

    response = completion.choices[0].message.content
    conversation.append({"role": "assistant", "content": response})
    user.need_history = conversation
    user.save()

    if "{" in response and "}" in response:
        print("ohhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh")

        response1 = response.index("{")
        response2 = response.index("}")
        response3 = response[response1:response2 + 1]
        response = json.loads(response3)

        print("formatted_JSON:", response, "----------------------------------------------------------------- \n")
        user.cleared = True
        user.need_history = []
        user.save()
        api_response = api_caller(api_address, response)
        return api_response
    user.cleared = False
    user.save()
    return response

@api_view(['POST'])
def futty(request):
    try:
        query = request.data.get('query')
        email = request.data.get('email')

        if not query:
            return Response({"status": 0, "message": "Missing query"})
        query = query.lower()

        if not email:
            return Response({"status": 0, "message": "Missing email"})
        user, created = Users.objects.get_or_create(email = email, defaults={'email': email})

        if created:
            user.final_searched_player = "FOOTY"
            user.need_history = []
            user.chat_history = []
            user.cleared = True
            user.save()

        name_prompt = f"""
I Will give you a text if you find any football player name or any person name in that question return exactly the name else return exactly 'NO'. Your main focus is to find if there is any football player name presents even if any nickname of football player present you have to find it.
eg:
1. text: 'What is James's price at the moment?' output: James
2.text: 'What is his ratings' output: NO

Let's get started. Remember don't add extra text, details or explaination whith output. text:{query}
"""

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": name_prompt}
            ]
        )
        name_response = completion.choices[0].message.content
        print("name:", name_response, "nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn")
        if(name_response != "NO" and user.final_searched_player != name_response) or ("cheap" in query or "expens" in query or "low" in query or "high" in query):
            user.final_searched_player = name_response
            user.cleared = True
            user.chat_history = []

            api_address = get_api_address(query)
            if not 'POST' in api_address:
                return Response({"AI": api_address, "status": 1,})
            
            user.final_api_address = api_address
            user.save()
            
            response = get_formated_json(api_address, query, user)

            if "success" in response:
                payload = response['success']['Results']
                system_prompt = f"You are Futty.ai, a specialized AI assistant and an integral part of FutAlert. Unlike OpenAI, my primary focus is on providing real-time information and guidance specifically related to the FIFA online game. Whether you're looking for the latest updates, tips, or game insights, I'm here to help enhance your FIFA gaming experience. Anything else is not your scope. List-json is the real time answer for the user query obtained from Futty API you have to answer user query by refering this List-json. List-json:{payload}. Remember don't use the word 'List-json' instead of that use the word 'FutAlert'."

                default_chat_history = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
                ]
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=default_chat_history
                )
                ai_response = completion.choices[0].message.content
                default_chat_history.append({"role": "assistant", "content": ai_response})
                user.chat_history = default_chat_history
                user.save()
                return Response({"AI": ai_response, "status": 1})

            else:
                user.last_query = query
                user.save()
                return Response({"AI": response, "status": 1})
            
        else:
            if not user.cleared:
                final_api_address = user.final_api_address
                user.need_history.append({"role": "user", "content": query})
                user.save()
                response = get_formated_json(final_api_address, query, user)
                if "success" in response:
                    payload = response['success']['Results']
                    system_prompt = f"You are Futty.ai, a specialized AI assistant and an integral part of FutAlert. Unlike OpenAI, my primary focus is on providing real-time information and guidance specifically related to the FIFA online game. Whether you're looking for the latest updates, tips, or game insights, I'm here to help enhance your FIFA gaming experience. Anything else is not your scope. List-json is the real time answer for the user query obtained from Futty API you have to answer user query by refering this List-json. List-json:{payload}."
                    default_chat_history = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user.last_query}
                    ]
                    completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=default_chat_history
                    )
                    response = completion.choices[0].message.content
                    default_chat_history.append({"role": "assistant", "content": response})
                    user.chat_history = default_chat_history
                    user.cleared = True
                    user.need_history = []
                    user.save()
                    return Response({"AI": response, "status": 1 })

                else:
                    return Response({"AI": response, "status": 1})
         
            else:
                conversation = user.chat_history
                print(conversation, "ccccccccccccccccccccccccccccccccccccc")
                if len(conversation) == 0:
                    print("thennnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn")
                    system_prompt = "You are Futty.ai, a specialized AI assistant and an integral part of FutAlert. Unlike OpenAI, my primary focus is on providing real-time information and guidance specifically related to the FIFA online game. Whether you're looking for the latest updates, tips, or game insights, I'm here to help enhance your FIFA gaming experience. Anything else is not your scope."
                    first_chat_history = [
                        {"role": "system", "content": system_prompt}
                    ]
                    conversation = first_chat_history
                print("nooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo")
                api_address = user.final_api_address
                conversation.append({"role": "user", "content": query})
                completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=conversation
                    )
                response = completion.choices[0].message.content
                conversation.append({"role": "assistant", "content": response})
                user.chat_history = conversation
                user.save()
                return Response({"AI": response, "status": 1})

            

        
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno

        message = f"""Error: {e}

File: {file_name}, Line: {line_number}"""
        
        return Response({"status": -1, "mesage": message})