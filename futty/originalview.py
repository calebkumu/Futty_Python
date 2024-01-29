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

#Setting OpenAI key
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

#Calls futty's API and return it's result
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
        print("Futt API Response:", data)
        return ({"success": data, "payload": payload}) 
    else:
        return ({"failiure": "Issues in processing you request please try again later or try another questions.","payload":payload})

#Generate prompt needed to create payload from user question
def json_formatter(api_address, question):
    #Header of the prompt
    prompt = """I will give you a question from that question you have to generate a JSON. 
The Fields for the JSON are given below, you have to generate JSON as descriped in Fields. Don't use the word 'JSON' in any of your output instead of that use the word 'response'.
Fields:
"""
    #Generating body of the prompt 
    fields = Fields.objects.filter(api_address = api_address) #Request param fields
    for field in fields:
        check = 0
        line = f"{field.field_name}: {field.field_type} field. "
        description = field.description if field.description.endswith('.') else field.description + '. '
        if field.required:
            ask = "*required. If not specified in question, before generating JSON get the value from user and then generate JSON."
        elif field.default_value:
            ask = f"If not specified in the question, use {field.default_value} as default value. Remember use {field.default_value} as default value."
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
            line = line + "\n \t User may provide CardTypeGroup or PlayerCardTypeInternalName or PlayerCardTypeName you have map it with PlayerCardTypeId and find corresponding PlayerCardType. To map use this table: \n" + formatted_output

        prompt = prompt + line + "\n"

    #Footer of the prompt
    end_msg = f"""Don't forget that you should not use the word 'JSON' in any of our response to user. Remember don't ask unnecessary questions if any fields is missing in the given question use default value provided in Field.""" 

    #returning final prompt
    prompt = prompt + end_msg
    print("prompt:", prompt)
    return(prompt)

#Finds and return API address needs to call for the given question
def get_api_address(question):
    end_points = list(End_points.objects.values_list('api_address', flat=True))
    descriptions = list(End_points.objects.values_list('description', flat=True))

    context = ""
    for i in range(0, len(end_points)):
        context = context + end_points[i]+". "
        context = context + descriptions[i]  + "\n"

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


#Generate and return payload from the question
def get_formated_json(api_address, question, user):
    api_address_id =  End_points.objects.get(api_address = api_address.replace(".", ""))

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
    print("JSON creator response:", response)
    conversation.append({"role": "assistant", "content": response})
    user.need_history = conversation
    user.save()

    if "{" in response and "}" in response:
        response1 = response.index("{")
        response2 = response.index("}")
        response3 = response[response1:response2 + 1]
        response = json.loads(response3)
        print("formatted_JSON:", response)
        user.cleared = True
        user.need_history = []
        user.save()

        api_response = api_caller(api_address, response)
        return api_response 
    
    if("size" or "Size" or "PlayerCardTypeId" or "playercardtypeid" in response):
        user.cleared = True
        user.final_searched_player = "Futty"
        user.need_history = []
        user.save()
        return ("Can't able to process your request right now. Please try again later or try another questions.") 
    
    user.cleared = False
    user.save()

    return response

#Futty API
@api_view(['POST'])
def futty(request):
    try:
        #Getting input from request data
        query = request.data.get('query')
        if not query:
            return Response({"status": 0, "message": "Missing query"})
        query = query.lower()

        """Note: Here it is done as single space. You can create separate space for each user once they loggedin using 
        email. It will help to maintain chat history and increase user experiance as AI can able to remember previous chat 
        which makes multi-turn conversations easy.
        
        Reffer loginview for create separate space for each user."""

        #WARNING: Create one user in user table if not already present!
        user = Users.objects.first()

        #To fix issues in recognising exact Son
        if " son" in query:
            query = query.replace("heung", "")
            query = query.replace("min", "")
            query = query.replace("son", "heung min son")

        #To find wheather user asking details of specific player
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
        print("name:", name_response)
    
        if(name_response != "NO") or ("cheap" in query or "expens" in query or "low" in query or "high" in query):
            user.final_searched_player = name_response
            user.cleared = True
            user.need_history = []
            user.chat_history = []

            #Finding which API needs to be called
            api_address = get_api_address(query)
            if not 'POST' in api_address:
                return Response({"AI": api_address.replace("JSON", ""), "status": 1,})
            user.final_api_address = api_address
            user.save()
            
            #Calling the API
            response = get_formated_json(api_address, query, user)
            if "success" in response:
                #If no data presents in API response
                if not response['success']['Results']:
                    user.cleared = True
                    user.final_searched_player = "Futty"
                    user.need_history = []
                    user.save()
                    return Response({"AI": "Can't able to process your request right now. Please try again later or try another questions.", "status": 1})

                payload = response['success']['Results']

                #To change the fields name PlayStation4 and Xbox
                for i in payload:
                    i.pop("CurrentPricePC")
                    i.pop("FacePhotoUrl")
                    i.pop("BadgePhotoUrl")
                    i.pop("NationPhotoUrl")
                    i.pop("PlayerFutwizId")
                    i["CurrentPriceOnPC"] = i.pop("CurrentPricePS4")
                    i["CurrentPriceOnConsole"] = i.pop("CurrentPriceXbox")
                
                #AI analyse the API response and answering to question
                system_prompt = f"You are Futty.ai, a specialized AI assistant and an integral part of FutAlert. Unlike OpenAI, my primary focus is on providing real-time information and guidance specifically related to the EA FC online game. Whether you're looking for the latest updates, real-time market prices of particular player, tips, or game insights, I'm here to help enhance your EA FC gaming experience. Anything else is not your scope. Don't mention or add any other website URL in your response.You are AI Model named Futty. NOT OPENAI GPT. You are representing FutAlert - EA FC game analytics company. FutAlert-JSON is the real time answer for the user query obtained from FutAlert's API you have to answer user query by refering this FutAlert-JSON. FutAlert-JSON may contain more than one player containing the given name at any where of the player full name which mean user entry wrong name by mistake in that case you have to ask for which player you are looking for? FutAlert-JSON:{payload}. If FutAlert-JSON is not empty which means the question is within our scope and you must answer for that question using informations present in FutAlert-JSON.  Remember don't use the word 'FutAlert-JSON' instead of that use the word 'FutAlert' in your response. Don't use any link in your response. Check if user queries relate to our business. if not, politely state it's outside our scope. Don't say anything like 'Let me check that for you' return answer only exact answer."

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
                return Response({"AI": ai_response.replace("-JSON", ""), "status": 1})
            
            if "failiure" in response:
                user.cleared = True
                user.need_history = []
                user.save()
                return Response({"AI": response['failiure'].replace("JSON", ""), "status": 1})

            else:
                if len(user.need_history) == 1:
                    user.last_query = query
                user.save()
                return Response({"AI": response.replace("JSON", ""), "status": 1})
            
        else:
            #If they had previous unasnwered question
            if not user.cleared:
                final_api_address = user.final_api_address
                user.need_history.append({"role": "user", "content": query})
                user.save()
                response = get_formated_json(final_api_address, query, user)
                if "success" in response:
                    if not response['success']['Results']:
                        user.cleared = True
                        user.final_searched_player = "Futty"
                        user.need_history = []
                        user.save()
                        return Response({"AI": "Can't able to process your request right now. Please try again later or try another questions.", "status": 1})
                    payload = response['success']['Results']
                    for i in payload:
                        i.pop("CurrentPricePC") 
                        i.pop("FacePhotoUrl")
                        i.pop("BadgePhotoUrl")
                        i.pop("NationPhotoUrl")
                        i.pop("PlayerFutwizId")
                        i["CurrentPriceOnConsole"] = i.pop("CurrentPriceXbox")
                        i["CurrentPriceOnPC"] = i.pop("CurrentPricePS4")                     
                    system_prompt = f"You are Futty.ai, a specialized AI assistant and an integral part of FutAlert. Unlike OpenAI, my primary focus is on providing real-time information and guidance specifically related to the EA FC online game. Whether you're looking for the latest updates, real-time market prices of particular player, tips, or game insights, I'm here to help enhance your EA FC gaming experience. Anything else is not your scope. Don't mention or add any other website URL in your response.You are AI Model named Futty. NOT OPENAI GPT. You are representing FutAlert - EA FC game analytics company. FutAlert-JSON is the real time answer for the user query obtained from FutAlert's API you have to answer user query by refering this FutAlert-JSON. FutAlert-JSON may contain more than one player containing the given name at any where of the player full name which mean user entry wrong name by mistake in that case you have to ask for which player you are looking for? FutAlert-JSON:{payload}. If FutAlert-JSON is not empty which means the question is within our scope and you must answer for that question using informations present in FutAlert-JSON.  Remember don't use the word 'FutAlert-JSON' instead of that use the word 'FutAlert' in your response. Don't use any link in your response. Check if user queries relate to our business. if not, politely state it's outside our scope. Don't say anything like 'Let me check that for you' return answer only exact answer."
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
                    return Response({"AI": response.replace("-JSON", ""), "status": 1 })
                
                if "failiure" in response:
                    user.cleared = True
                    user.need_history = []
                    user.save()
                    return Response({"AI": ai_response['failiure'].replace("JSON", ""), "status": 1})

                else:
                    if len(user.need_history) == 1:
                        user.last_query = query
                    user.save()
                    return Response({"AI": response.replace("JSON", ""), "status": 1})
            #To get proper rejection content from AI
            else:
                conversation = user.chat_history
                if len(conversation) == 0:
                    system_prompt = "You are Futty.ai, a specialized AI assistant and an integral part of FutAlert. Unlike OpenAI, my primary focus is on providing real-time information and guidance specifically related to the EA FC online game. Whether you're looking for the latest updates, real-time market prices of particular player, tips, or game insights, I'm here to help enhance your EA FC gaming experience. Anything else is not your scope. Don't mention or add any other website URL in your response.You are AI Model named Futty. NOT OPENAI GPT. You are representing FutAlert - EA FC game analytics company. FutAlert-JSON is the real time answer for the user query obtained from FutAlert's API you have to answer user query by refering this FutAlert-JSON. FutAlert-JSON may contain more than one player containing the given name at any where of the player full name which mean user entry wrong name by mistake in that case you have to ask for which player you are looking for? FutAlert-JSON:{payload}. If FutAlert-JSON is not empty which means the question is within our scope and you must answer for that question using informations present in FutAlert-JSON.  Remember don't use the word 'FutAlert-JSON' instead of that use the word 'FutAlert' in your response. Don't use any link in your response. Check if user queries relate to our business. if not, politely state it's outside our scope. Don't say anything like 'Let me check that for you' return answer only exact answer."
                    first_chat_history = [
                        {"role": "system", "content": system_prompt}
                    ]
                    conversation = first_chat_history
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
                return Response({"AI": response.replace("-JSON", ""), "status": 1})
    
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno

        message = f"""Error: {e}

File: {file_name}, Line: {line_number}"""
        
        return Response({"status": -1, "mesage": message})