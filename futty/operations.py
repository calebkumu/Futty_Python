"""
write your openai calling functions here 
"""

import openai
import os
from dotenv import load_dotenv
import json

from . import prompts as pr
from . import helpers as hlp
from . models import End_points, Fields

# Setting api key
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

#Basic openai calling
def basic_gpt(question, multi = False):
    with open("futty/config.json", 'r') as config_file:
        config = json.load(config_file)
    option = config['choice']
    if option > 0 and multi == True:
        with open("futty/config.json", 'r') as config_file:
            config = json.load(config_file)
        datas = config['list']
        prompt = pr.OPTION_TEXT.format(option = question, list = datas)

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

    else:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": question}
            ]
        )
    response = completion.choices[0].message.content

    return response


#To find api to be called
def api_address(question):

    try:
        int(question)
        a = True
    except ValueError:
        a =  False

    with open("futty/config.json", 'r') as config_file:
        config = json.load(config_file)
    conversation = config['conversation']

    option = config['choice']
    if option > 0 and a == True:
        response = basic_gpt(option, multi=True)
        return response

    if len(conversation) > 1:
        #List all api end points from db
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
        if not api_address.startswith("POST"):
            api_address = "continue"

        return api_address

    #List all api end points from db
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
    config['api_address'] = api_address.replace(".", "")
    print("API_address:", api_address, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n \n")
    with open('futty/config.json', 'w') as config_file:
           json.dump(config, config_file, indent=4)

    return api_address


#Generate JSON and get response from FUT Alert apo
def formated_json(api_address, question):

    if not "POST" in api_address:
        with open("futty/config.json", 'r') as config_file:
            config = json.load(config_file)
        conversation = config['conversation']

        prompt = question
        conversation.append({"role": "user", "content": prompt})
        config['conversation'] = conversation
        with open('futty/config.json', 'w') as config_file:
           json.dump(config, config_file, indent=4)

        completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            messages = conversation,
            temperature = 0.7,
            top_p = 1.0,
        )
    else:
        api_address.replace(".", "")
        api_address_id =  End_points.objects.get(api_address = api_address)

        with open("futty/config.json", 'r') as config_file:
            config = json.load(config_file)
        conversation = config['conversation']

        if len(conversation) == 1:
            prompt = pr.json_formatter(api_address_id.id, question)
            conversation.append({"role": "user", "content": prompt})
            config['conversation'] = conversation
            with open('futty/config.json', 'w') as config_file:
               json.dump(config, config_file, indent=4)

        completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            messages = conversation,
            temperature = 0.7,
            top_p = 1.0,
        )

    response = completion.choices[0].message.content

    if "{" in response and "}" in response:

        with open("futty/config.json", 'r') as config_file:
            config = json.load(config_file)
        conversation = config['conversation']

        conversation = conversation[0:1]
        config['conversation'] = conversation
        with open('futty/config.json', 'w') as config_file:
           json.dump(config, config_file, indent=4)

        response1 = response.index("{")
        response2 = response.index("}")
        response3 = response[response1:response2 + 1]
        response = json.loads(response3)

        print("formatted_JSON:", response, "----------------------------------------------------------------- \n \n")
        api_response = hlp.api_caller(api_address, response)
        return api_response
    
    with open("futty/config.json", 'r') as config_file:
        config = json.load(config_file)
    conversation = config['conversation']
    conversation = conversation[0:1]
    config['conversation'] = conversation
    config['list'] = []
    with open('futty/config.json', 'w') as config_file:
       json.dump(config, config_file, indent=4)
    
    return {"failiure": response, "api_address": api_address}

