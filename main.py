import os
from collections import defaultdict

import re
from openai import OpenAI
from difflib import SequenceMatcher

from bpmn import BPMN
from read_bpmn import read_bpmn
from vis import view_bpmn

rule_file = r".\LPD4VR-master\rules.txt"  # Path to the file containing the regulations
bpmn_folder_path = r".\LPD4VR-master\violance"  # Directory path containing the BPMN 2.0 business process models


# bpmn_folder_path = r".\LPD4VR-master\compliance"  # Directory path containing the BPMN 2.0 business process models

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key = os.environ.get("OPENAI_API_KEY")
)

def chat_LLM(prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
             "content": "You are an assistant specialized in compliance checking for business process models."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                ],
            }
        ],
        max_completion_tokens=1024,
        temperature = 0.5,
        # logprobs = True,
        # top_logprobs = 3
    )
    # import numpy as np
    # print(np.exp(response.choices[0].logprobs.content[0].top_logprobs[0].logprob))
    # print(response.choices[0].logprobs.content[0].top_logprobs)

    return response.choices[0].message.content.strip()


def combine_strings(strings):
    '''
    Formating a list of strings into a single string where each item is enclosed in single quotation marks and separated by commas, with the final item preceded by the word "and".    :param strings:
    :return: list of strings
    '''
    if len(strings) == 0:
        return ""
    elif len(strings) == 1:
        return f"'{strings[0]}'"
    else:
        return ", ".join(f"'{s}'" for s in strings[:-1]) + f" and '{strings[-1]}'"


def extract_list_from_str(input_string):
    # 提取列表内容并转换为 Python 列表
    if len(input_string) < 3:
        return []
    try:
        # 使用正则表达式提取中括号内的内容
        match = re.search(r'\[.*?\]', input_string)
        if match:
            list_str = match.group(0)  # 提取列表部分
            python_list = list_str[1:-1].split(', ')
            return python_list
        else:
            return []
    except (ValueError, SyntaxError) as e:
        return []

def sentence_participantName2actNameList(participantName2actNameList):
    sentence = ''
    for k, v in participantName2actNameList.items():
        sentence += f"The participant '{k}' is responsible for the following activities: {str(v)}; "
    sentence = sentence[:-2] + '.'
    return sentence


def find_most_similar_index(target_act_name, act_name_list):
    """
    index target_act_name in act_name_list
    """
    if target_act_name in act_name_list:
        index = act_name_list.index(target_act_name)
        return index
    else:
        max_similarity = 0
        most_similar_index = -1

        for index, string in enumerate(act_name_list):
            similarity = SequenceMatcher(None, target_act_name, string).ratio()
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_index = index

        return most_similar_index


def dfs(node, visited):
    if node in visited:
        return
    # 访问当前节点
    # print(f"Visiting node: {node.name}")
    visited.add(node)  # 将当前节点标记为已访问

    # 遍历当前节点的所有子节点
    for i in range(len(node.out_arcs)):
        next_node = node.out_arcs[i].target
        dfs(next_node, visited)

def find_earlist_act(act_list):
    for act in act_list:
        visited = set()
        dfs(act, visited)
        if set(act_list) <= visited:
            return act


def process2nl(node, visited, then_flag=False, branch_depth=0):
    if visited.count(node) > 1:
        return ''

    sentence = ""

    visited.append(node)
    # print(node)
    # print(branch_depth)
    if isinstance(node, BPMN.EndEvent):
        sentence += f"The process ends. "

    if isinstance(node, BPMN.StartEvent):
        for i, arc in enumerate(node.out_arcs):
            next_node = arc.target
            gen_sentence = process2nl(next_node, visited, True, branch_depth)
            sentence += gen_sentence

    if isinstance(node, BPMN.Task):
        if len(node.in_arcs) > 0 and len([True for arc in node.in_arcs if isinstance(arc.source, BPMN.StartEvent)]) > 0:
            sentence += f"The process starts with the activity '{node.name}'. "
        else:
            # if not isinstance(node, BPMN.Event):
            if not then_flag:
                sentence += f"The activity '{node.name}' is executed. "
            else:
                sentence += f"Then the activity '{node.name}' is executed. "

        dataOutObjs = [arc.target for arc in node.out_arcs if
                       isinstance(arc.target, BPMN.dataObjectReference)]
        dataInObjs = [arc.source for arc in node.in_arcs if
                      isinstance(arc.source, BPMN.dataObjectReference)]

        Outacts_datas = defaultdict(list)
        for dataObj in dataOutObjs:
            for dataRef_out_arc in dataObj.out_arcs:
                Outacts_datas[dataRef_out_arc.target.name].append(dataObj.name)
        Inacts_datas = defaultdict(list)
        for dataObj in dataInObjs:
            for dataObj_in_arc in dataObj.in_arcs:
                Inacts_datas[dataObj_in_arc.source.name].append(dataObj.name)

        if len(dataInObjs) > 0:
            sentence += f"During this activity, "
            for act, objs in Inacts_datas.items():
                sentence += f"data including {combine_strings(objs)} is received from the activity '{act}'; "
            sentence = sentence[:-2] + '. '
        if len(dataOutObjs) > 0:
            sentence += f"During this activity, "
            for act, objs in Outacts_datas.items():
                sentence += f"data including {combine_strings(objs)} is transferred to the activity '{act}' for further processing; "
            sentence = sentence[:-2] + '. '

        dataInStores = [arc.source for arc in node.in_arcs if
                        isinstance(arc.source, BPMN.dataStoreReference)]
        dataOutStores = [arc.target for arc in node.out_arcs if
                         isinstance(arc.target, BPMN.dataStoreReference)]

        if len(dataInStores) > 0:
            sentence += f"During this activity, "
            for dataInStore in dataInStores:
                sentence += f"data will be retrieved from the data store '{dataInStore.name}'; "
            sentence = sentence[:-2] + '. '

        if len(dataOutStores) > 0:
            sentence += f"During this activity, "
            for dataOutStore in dataOutStores:
                sentence += f"data will be saved into the data store '{dataOutStore.name}'; "
            sentence = sentence[:-2] + '. '

        for i, arc in enumerate(node.out_arcs):
            next_node = arc.target
            gen_sentence = process2nl(next_node, visited, True, branch_depth)
            sentence += gen_sentence

    if isinstance(node, BPMN.ExclusiveGateway):
        ques = node.name
        if branch_depth == 0:
            sentence += f"Then process splits into {len(node.out_arcs)} branches, with only one branch selected based on the evaluation of '{ques}'. "
        else:
            sentence += f"Then process splits again into {len(node.out_arcs)} branches, with only one branch selected based on the evaluation of '{ques}'. "
        for i, next_arc in enumerate(node.out_arcs):
            gen_sentence = process2nl(next_arc.target, visited,
                                      False, branch_depth + 1)
            if gen_sentence is not None:
                sentence += '\n ' + '-' * branch_depth + f"If the answer is '{next_arc._Flow__name}', branch {i} is executed: {gen_sentence}"
    elif isinstance(node, BPMN.InclusiveGateway):
        ques = node.name
        if branch_depth == 0:
            sentence += f"Then process splits into {len(node.out_arcs)} branches, and one or more branches are selected based on the evaluation of '{ques}'. "
        else:
            sentence += f"Then process splits again into {len(node.out_arcs)} branches, and one or more branches are selected based on the evaluation of '{ques}'. "
        for i, next_arc in enumerate(node.out_arcs):
            gen_sentence = process2nl(next_arc.target, visited,
                                      False, branch_depth + 1)
            if gen_sentence is not None:
                sentence += '\n ' + '-' * branch_depth + f"If the answer is '{next_arc.name}', branch {i} is executed: {gen_sentence}"
    elif isinstance(node, BPMN.ParallelGateway):
        if branch_depth == 0:
            sentence += f"Then the process splits into {len(node.out_arcs)} parallel branches: "
        else:
            sentence += f"Then the process splits again into {len(node.out_arcs)} parallel branches: "
        for i, next_arc in enumerate(node.out_arcs):
            gen_sentence = process2nl(next_arc.target, visited,
                                      False, branch_depth + 1)
            if gen_sentence is not None:
                sentence += '\n ' + '-' * branch_depth + f"The branch {i} is: {gen_sentence}"

    return sentence


def if_Violation(bpmn_model, rule):
    process_name, _ = os.path.splitext(os.path.basename(bpmn_path))

    participantRef2Name = {node.process_ref: node.name for node in list(bpmn_model.get_nodes()) if
                           type(node) is BPMN.Participant}

    start_events = [node for node in list(bpmn_model.get_nodes()) if isinstance(node, BPMN.StartEvent)]

    if len(start_events) > 1:
        return True, 'Violation. The process model has multiple start events.'
    else:
        start_event = start_events[0]

    visited = []
    process_nl = process2nl(start_event, visited, False)

    acts = [node for node in set(visited) if
            (isinstance(node, BPMN.Task) or isinstance(node, BPMN.Gateway)) and len(node.name) > 0]

    participantName2actNameList = defaultdict(list)
    for act in acts:
        participantName2actNameList[participantRef2Name[act.process]].append(act.name)

    #few-shot
    query_vio = (f"I will provide you with a collaborative process and a regulation. Your task is to judge whether the process complies with the regulation. If the process is unrelated to the regulation, consider it as compliant. During the judgment phase, it is crucial to carefully consider the participants involved in each activity. I will begin by providing some examples."
                 f"\n ##Example Process Details: The process focuses on MedicalInstitutionAccessApproval. Within the process, the participant 'Internet healthcare service platform provider' is responsible for the following activities: ['Qualification verification', 'Does it meet the access specification?', 'Notification of non-compliance with validation', 'Open platform entry privileges']; The participant 'medical institutions' is responsible for the following activities: ['Improve institutional information', 'Submit an access request', 'Upload qualification materials']. \n The process starts with the activity 'Submit an access request'. Then the activity 'Upload qualification materials' is executed. During this activity, data including 'ACEMI', 'MTPL', 'SDSNL', 'RSL', 'CMAR' and 'ICPL' are transferred to the activity 'Qualification verification' for further processing. Then the activity 'Qualification verification' is executed. During this activity, data including 'ACEMI', 'MTPL', 'SDSNL', 'RSL', 'CMAR' and 'ICPL' are received from the activity 'Upload qualification materials'. Then process splits into 2 branches, with only one branch selected based on the evaluation of 'Does it meet the access specification?'. \n If the answer is 'no', branch 0 is executed: The activity 'Notification of non-compliance with validation' is executed. The process ends. \n If the answer is 'yes', branch 1 is executed: The activity 'Open platform entry privileges' is executed. Then the activity 'Improve institutional information' is executed. The process ends. "
                 f"\n ##Example Regulations and Evaluations: "
                 f"\n #Regulation: If the pharmacy does not perform prescription verification, it is a violation process. #Evaluation: This process is unrelated to the retrieval of drugs from the pharmacy; therefore, the answer is Compliance."
                 f"\n #Regulation: The upload of medical staff qualification materials must include PQC and PPC, otherwise it will be judged as a violation process. #Evaluation: The process is not related to medical staff qualifications; therefore, the answer is Compliance."
                 f"\n #Regulation: The upload of medical institution qualification materials must include ACEMI, MTPL, SDSNL, LMDCL, RDTL, RSL, SCPND&FPS, CMAR, ICPL, otherwise it will be judged as a violation process. #Evaluation: The process violates the Regulation because the upload of medical institution qualification materials does not include the mandatory data 'LMDCL', 'RDTL', and 'SCPND&FPS'."
                 f"\n ##Input Process and Regulation: "
                 f"\n #Process Details: The process focuses on {process_name}. Within the process, {'t' + sentence_participantName2actNameList(participantName2actNameList)[1:]} \n {process_nl}"
                 f"\n #Regulation: {rule}"
                 f"\n ###Instructions: If the process complies with the regulation, provide the one-word feedback: 'Compliance'. If the process violates the regulation, respond with 'Violation', followed by an explanation.")

    #zero-shot
    # query_vio = (f"I will provide you with a collaborative process and a regulation. Your task is to judge whether the process complies with the regulation. If the process is unrelated to the rule, consider it as compliant. During the judgment phase, it is crucial to carefully consider the participants involved in each activity."
    #              f"\n ##Input Process and Regulation: "
    #              f"\n #Process Details: The process focuses on {process_name}. Within the process, {'t' + sentence_participantName2actNameList(participantName2actNameList)[1:]} \n {process_nl}"
    #              f"\n #Regulation: {rule}"
    #              f"\n ###Instructions: If the process complies with the regulation, provide the one-word feedback: 'Compliance'. If the process violates the regulation, respond with 'Violation', followed by an explanation.")

    # print(query_vio)
    res = chat_LLM(query_vio)
    # print('-' * 20)
    # print("Response: " + res)
    # print('*' * 20)
    if res == 'Compliance' or res == 'Compliance.':
        return False, None
    else:
        return True, res


def Violation_recognition(bpmn_file, rule_file):
    try:
        bpmn_model = read_bpmn(bpmn_file)
    except Exception as e:
        print(e)
        return {'Incomplete BPMN model.':e}

    # view_bpmn(bpmn_model)

    rules = []
    with open(rule_file, 'r', encoding='utf-8') as file:
        for line in file:
            rules.append(line.strip())

    violations = {}  # key is the rules, values is the reason for violation

    for rule in rules:
        vio_pred, reason = if_Violation(bpmn_model, rule)
        if vio_pred:
            violations[rule] = reason

    return violations

if __name__ == '__main__':
    files = os.listdir(bpmn_folder_path)

    # 只保留文件（排除文件夹）
    files = sorted([file for file in files if os.path.isfile(os.path.join(bpmn_folder_path, file))])

    number_of_violation = 0
    number_of_compliant = 0
    for file in files:
        bpmn_path = os.path.join(bpmn_folder_path, file)
        print(bpmn_path)
        violations = Violation_recognition(bpmn_path, rule_file)
        if len(violations) > 0:
            print('This process violates the following regulations along with their corresponding reasons:')
            for k, v in violations.items():
                print(f'##Regulation: {k}')
                print(f'##Reason for Violation: {v}')
            number_of_violation += 1
        else:
            number_of_compliant += 1
            print('This process complies with all regulations.')
        print('-' * 20)
    print(f'Number of violated process models: {number_of_violation}; Number of compliant process models: {number_of_compliant}')
