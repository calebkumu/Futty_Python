#Write your prompts here

import csv

from . models import Fields


# To find which api to be called
API_FINDER = """API_list:{api_list} 
I will give you a question you have to analyse the question and find which api is suitable for the given question.

eg:
question:
What is the cheapest 83 rated gold player?
output:
POST api/Player/GetCheapestorMostExpensivePlayers

let's get started! remember your response must contain only api. Don't add extra senetences.

question: {question}.
"""
