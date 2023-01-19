import json
import xmltodict

class SIMULINK_BLOCK:
    # Class attribute
    def __init__(self, id, previous, block_name):
        self.id = id
        self.previous = previous
        self.block_name = block_name

flag = False
sourceType = ""
name = ""
sid = ""
simulink_blocks_list = []
connections_list = []
source_block_list = []
list_of_SIDs = []
contourNodes = []
list_of_supported_blocks = ["Ideal Switch", "Voltage Measurement", "Current Measurement"]
srcBlock = ""
dstBlock = []
taskNodes = []
OPCUAscript = ""
startNodeID = 30001
marker = 0

def analyseNastedBranch(list, accum):
    if "Branch" in list:
        for item in list["Branch"]:
            accum = analyseNastedBranch(item, accum)
    else:
        if "P" in list:
            for item in list["P"]:
                if item['@Name'] == "DstBlock":
                    accum.append(item["#text"].replace("\n",""))
    return accum

with open("model_xml.xml") as xml_file:
    data_dict = xmltodict.parse(xml_file.read())
    json_data = json.dumps(data_dict)
    
    for x in data_dict["ModelInformation"]["Model"]["System"]["Block"]:
        flag = False
        name = x["@Name"].replace("\n","")
        sid = x["@SID"]
        for item in x["P"]:
            if '@Name' in item:
                if item['@Name'] == "SourceType":
                    sourceType = item["#text"].replace("\n","")
                    if sourceType == "Ground":
                        sid = "0"
                    flag = True
        if not flag:
            sourceType = "No Source Type"
        simulink_blocks_list.append({'name' : name, 'sourceType' : sourceType, 'SID' : sid})

    for item in simulink_blocks_list:
        print(item)

    for x in data_dict["ModelInformation"]["Model"]["System"]["Block"]:   
        if "InstanceData" in x:
            for item in x["InstanceData"]["P"]:
                sourcetype = simulink_blocks_list[marker]["sourceType"]
                if sourcetype == "Current Measurement":
                    if item['@Name'] == "OutputType":
                        simulink_blocks_list[marker].update({'OutputType': item["#text"].replace("\n","")})
                elif sourcetype == "Voltage Measurement":
                    if item['@Name'] == "OutputType":
                        simulink_blocks_list[marker].update({'OutputType': item["#text"].replace("\n","")})
                elif sourcetype == "Ideal Switch":
                    if item['@Name'] == "Ron":
                        simulink_blocks_list[marker].update({'Ron': item["#text"].replace("\n","")})
                    elif item['@Name'] == "Lon":
                        simulink_blocks_list[marker].update({'Lon': item["#text"].replace("\n","")})
                    elif item['@Name'] == "Rs":
                        simulink_blocks_list[marker].update({'Rs': item["#text"].replace("\n","")})
                elif sourcetype == "AC Voltage Source":
                    if item['@Name'] == "Amplitude":
                        simulink_blocks_list[marker].update({'Amplitude': item["#text"].replace("\n","")})
                    elif item['@Name'] == "Frequency":
                        simulink_blocks_list[marker].update({'Frequency': item["#text"].replace("\n","")})
                    elif item['@Name'] == "Phase":
                        simulink_blocks_list[marker].update({'Phase': item["#text"].replace("\n","")})

        if "Port" in x:
            if "P" in x["Port"]:
                for item in x["Port"]["P"]:
                    if sourcetype == "Current Measurement":
                        if item['@Name'] == "Name":
                            simulink_blocks_list[marker].update({'SignalName': item["#text"].replace("\n","")})
                    elif sourcetype == "Voltage Measurement":
                        if item['@Name'] == "Name":
                            simulink_blocks_list[marker].update({'SignalName': item["#text"].replace("\n","")})

        marker = marker + 1

    for x in data_dict["ModelInformation"]["Model"]["System"]["Line"]:
        if "@LineType" in x:
            if "P" in x:
                for item in x["P"]:
                    if item['@Name'] == "SrcBlock":
                        srcBlock = item["#text"].replace("\n","")
                    elif item['@Name'] == "DstBlock":
                        dstBlock.append(item["#text"].replace("\n",""))
            if "Branch" in x:
                for item in x["Branch"]:
                    if not "Branch" in item:
                        if "P" in item:
                            for i in item["P"]:
                                if i['@Name'] == "DstBlock":
                                    dstBlock.append(i["#text"].replace("\n",""))
                    else:
                        dstBlock = analyseNastedBranch(item, dstBlock)
            connections_list.append({'src':srcBlock,'dst':dstBlock})
            dstBlock = []



for item in connections_list:
    print(item)

def findSID(simulink_list,block_name):
    sid = -1
    for item in simulink_list:
        if block_name in item["name"]:
            sid = item["SID"]
            break
    return sid

def findSourceTypeFromSID(simulink_list,sid):
    sourcetype = ""
    for item in simulink_list:
        if item["SID"] == sid:
            sourcetype = item["sourceType"]
            break
    return sourcetype

def addSID(array,sid):
    array.append(int(sid))
    return array

def checkContour(array, array2, newSID, parent):
    accum = array.copy()
    accum2 = array2.copy()

    accum.append(int(newSID))
    accum = set([x for x in accum if accum.count(x) > 1])

    accum2.append(int(newSID))
    accum2 = set([x for x in accum2 if accum2.count(x) > 1])

    if len(accum) > 0 or len(accum2) > 0:
        print("Contour is detected when the new SID "+ newSID +" has been added!")
        while not parent == None:
            print("SID: "+str(parent.id)+", Block Name: "+parent.block_name)  
            if not parent.id in array:
                array.append(parent.id)
            if parent.id == int(newSID):
                break
            parent = parent.previous
        return True, array, array2
    else:
        print("New SID "+ newSID +" has been added. No contour detected!")
        return False, array, array2

for item in simulink_blocks_list:
    if item["sourceType"] == "AC Voltage Source":
        var = "my_variable_"+item["SID"]
        list_of_SIDs = addSID(list_of_SIDs,item["SID"])
        globals()[var] = SIMULINK_BLOCK(int(item["SID"]), None, item["name"])
        source_block_list.append(item["name"].replace("\n",""))

local_srcBlock = source_block_list[0]

def analyseConnectionsList(connections_list,local_srcBlock):
    global list_of_SIDs
    global contourNodes
    global taskNodes
    for item in connections_list:
        if item["src"] == local_srcBlock:
            length = len(item["dst"])
            while length >= 1:
                sid_block = findSID(simulink_blocks_list, item["dst"][length - 1])
                if not sid_block == -1:
                    var = "my_variable_"+sid_block
                else:
                    print("ERROR. Unknown SID of block the "+item["dst"][length - 1])
                sid = findSID(simulink_blocks_list,local_srcBlock)
                if not sid == -1:  
                    flag, contourNodes, list_of_SIDs = checkContour(contourNodes, list_of_SIDs, sid_block, globals()["my_variable_"+sid])
                    if flag == False:
                        if not int(sid_block) == 0:
                            taskNodes.append(sid_block)
                        list_of_SIDs = addSID(list_of_SIDs,sid_block)
                        globals()[var] = SIMULINK_BLOCK(int(sid_block), globals()["my_variable_"+sid], item["dst"][length - 1])
                else:
                    print("ERROR. Unknown SID of block the "+local_srcBlock)
                length = length - 1
            connections_list.pop(connections_list.index(item))
            break
        else:
            if local_srcBlock in item["dst"]:
                item["dst"].pop(item["dst"].index(local_srcBlock))
                length = len(item["dst"])
                if length > 0:
                    while length >= 1:
                        sid_block = findSID(simulink_blocks_list, item["dst"][length - 1])
                        if not sid_block == -1:
                            var = "my_variable_"+sid_block
                        else:
                            print("ERROR. Unknown SID of block the "+item["dst"][length - 1])
                        sid = findSID(simulink_blocks_list,local_srcBlock)
                        if not sid == -1:
                            flag, contourNodes,list_of_SIDs = checkContour(contourNodes, list_of_SIDs, sid_block, globals()["my_variable_"+sid])
                            if flag == False:
                                if not int(sid_block) == 0:
                                    taskNodes.append(sid_block)
                                list_of_SIDs = addSID(list_of_SIDs,sid_block)
                                globals()[var] = SIMULINK_BLOCK(int(sid_block), globals()["my_variable_"+sid], item["dst"][length - 1])                        
                        else:
                            print("ERROR. Unknown SID of block the "+local_srcBlock)
                        break
                        length = length - 1
                        item["dst"].pop(length - 1)
                sid_block = findSID(simulink_blocks_list,item["src"])
                if not sid_block == -1:
                    var = "my_variable_"+sid_block
                else:
                    print("ERROR. Unknown SID of block the "+item["src"])        
                sid = findSID(simulink_blocks_list, local_srcBlock)
                if not sid == -1:
                    flag, contourNodes, list_of_SIDs = checkContour(contourNodes, list_of_SIDs, sid_block, globals()["my_variable_"+sid])
                    if flag == False:
                        if not int(sid_block) == 0:
                            taskNodes.append(sid_block)
                        list_of_SIDs = addSID(list_of_SIDs,sid_block) 
                        globals()[var] = SIMULINK_BLOCK(int(sid_block), globals()["my_variable_"+sid], item["src"])            
                else:
                    print("ERROR. Unknown SID of block the "+local_srcBlock)
                connections_list.pop(connections_list.index(item))
                break

print("================ INITIAL LIST ====================")

for item in connections_list:
    print(item)

print("============= END OF INITIAL LIST ================")

analyseConnectionsList(connections_list,local_srcBlock)
analyseConnectionsList(connections_list,local_srcBlock)

iteration = 3

while len(connections_list) > 0:
    print("================ ITERATION "+str(iteration)+" ====================")
    for item in connections_list:
        print(item)

    print (taskNodes)
    nodeID = taskNodes.pop(0);
    print (globals()['my_variable_'+nodeID].block_name)
    analyseConnectionsList(connections_list,globals()['my_variable_'+nodeID].block_name)
    iteration = iteration + 1


def generate_xml_header(script, headNodeID, simulink_blocks, blocks_stack):
    script = """<?xml version="1.0" encoding="utf-8"?>
    <UANodeSet xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" Version="1.02" LastModified="2013-03-06T05:36:44.0862658Z" xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">"
    <UAObject NodeId="i="""+str(startNodeID)+"""" BrowseName="SIMULINK model">
        <Description>Generated OPC UA Information Model</Description>
        <References>
            <Reference ReferenceType="HasTypeDefinition">i=58</Reference>
            <Reference ReferenceType="Organizes" IsForward="false">i=85</Reference>
        </References>
    </UAObject>

    """
    script = convertSIM2OPCUA(script, headNodeID, simulink_blocks, blocks_stack)

    script += """</UANodeSet>"""
    f = open("simulink_opcua.xml", "w")
    f.write(script)
    f.close()
    return script

def addUANode(local_script, HeadNodeID, StartNodeID, UAObject, UADescription, UAProperties, UAVariables):
    nodeID = 0
    local_script += """<UAObject NodeId="i="""+str(StartNodeID)+"""" BrowseName=\""""+ UAObject +"""\">
        <DisplayName>"""+ UAObject +"""</DisplayName>
        <Description>SourceType: """+UADescription["sourceType"]+"""</Description>
        <Description>SID: """+UADescription["SID"]+"""</Description>
        <References>
            <Reference ReferenceType="Organizes" IsForward="false">i="""+str(HeadNodeID)+"""</Reference>
            <Reference ReferenceType="HasTypeDefinition">i=58</Reference>
        </References>
    </UAObject>
    
    """
    if len(UAProperties) > 0:
        nodeID = StartNodeID + 1
        local_script += """<UAObject NodeId="i="""+str(nodeID)+"""" BrowseName="Properties">
        <Description>"""+UAObject+""" properties </Description>
        <References>
            <Reference ReferenceType="Organizes" IsForward="false">i="""+str(StartNodeID)+"""</Reference>
            <Reference ReferenceType="HasTypeDefinition">i=58</Reference>
        </References>
    </UAObject>
    
    """
        parentNodeID = nodeID
        for item in UAProperties:
            nodeID = nodeID + 1
            local_script += """<UAVariable NodeId="i="""+str(nodeID)+"""" BrowseName=\""""+item+"""\" DataType="String" AccessLevel="3" UserAccessLevel="1">
        <References>
            <Reference ReferenceType="HasTypeDefinition">i=68</Reference>
            <Reference ReferenceType="Organizes" IsForward="false">i="""+str(parentNodeID)+"""</Reference>
        </References>
        <Value>
            <String>"""+UAProperties[item]+"""</String>
        </Value>
    </UAVariable>
    
    """

    if len(UAVariables) > 0:
        if nodeID == 0:
            nodeID = StartNodeID + 1
        else:
            nodeID = nodeID + 1
        local_script += """<UAObject NodeId="i="""+str(nodeID)+"""" BrowseName="Variables">
        <Description>"""+UAObject+""" variables </Description>
        <References>
            <Reference ReferenceType="Organizes" IsForward="false">i="""+str(StartNodeID)+"""</Reference>
            <Reference ReferenceType="HasTypeDefinition">i=58</Reference>
        </References>
    </UAObject>
    
    """
  
        iter = 0
        parentNodeID = nodeID
        for item in UAVariables:
            nodeID = nodeID + 1
            local_script += """<UAVariable NodeId="i="""+str(nodeID)+"""" BrowseName=\""""+item+"""\" DataType="String" AccessLevel="3" UserAccessLevel="1">
        <References>
            <Reference ReferenceType="HasTypeDefinition">i=62</Reference>
            <Reference ReferenceType="Organizes" IsForward="false">i="""+str(parentNodeID)+"""</Reference>
        </References>
        <Value>
            <String>"""+UAVariables[item]+"""</String>
        </Value>
    </UAVariable>
    
    """
    return local_script, nodeID

def convertSIM2OPCUA(script_with_header, headNodeID, simulink_blocks, blocks_stack):   
    local_script = script_with_header
    localStartNodeID = headNodeID

    for item in blocks_stack:
        sourcetype = findSourceTypeFromSID(simulink_blocks, str(item))
        if sourcetype == "AC Voltage Source":
            for block in simulink_blocks:
                if block["SID"] == str(item):
                    UAObject = block['name']
                    UADescription = {'sourceType': block['sourceType'], 'SID': block['SID']}
                    UAProperties = []
                    UAVariables = {'Amplitude': block['Amplitude'], 'Phase': block['Phase'], 'Frequency': block['Frequency']}
                    local_script, localStartNodeID = addUANode(local_script, headNodeID, (localStartNodeID+1), UAObject, UADescription, UAProperties, UAVariables)
    
    for item in blocks_stack:
        sourcetype = findSourceTypeFromSID(simulink_blocks, str(item))
        if sourcetype in list_of_supported_blocks:
            for block in simulink_blocks:
                if block["SID"] == str(item):
                    if sourcetype == "Current Measurement":
                        UAObject = block['name']
                        UADescription = {'sourceType': block['sourceType'], 'SID': block['SID']}
                        UAProperties = {'OutputType': block['OutputType']}
                        UAVariables = {'SignalName': block['SignalName']}
                        local_script, localStartNodeID = addUANode(local_script, headNodeID, (localStartNodeID+1), UAObject, UADescription, UAProperties, UAVariables)
                    elif sourcetype == "Voltage Measurement":
                        UAObject = block['name']
                        UADescription = {'sourceType': block['sourceType'], 'SID': block['SID']}
                        UAProperties = {'OutputType': block['OutputType']}
                        UAVariables = {'SignalName': block['SignalName']}
                        local_script, localStartNodeID = addUANode(local_script, headNodeID, (localStartNodeID+1), UAObject, UADescription, UAProperties, UAVariables)
                    elif sourcetype == "Ideal Switch":
                        UAObject = block['name']
                        UADescription = {'sourceType': block['sourceType'], 'SID': block['SID']}
                        UAProperties = {'Ron': block['Ron'], 'Lon': block['Lon'], 'Rs': block['Rs']}
                        UAVariables = {'control': 'signal1'}
                        local_script, localStartNodeID = addUANode(local_script, headNodeID, (localStartNodeID+1), UAObject, UADescription, UAProperties, UAVariables)
    return local_script

OPCUAscript = generate_xml_header(OPCUAscript, startNodeID, simulink_blocks_list, contourNodes)
