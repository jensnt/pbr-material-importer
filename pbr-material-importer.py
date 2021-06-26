# PBR Material Importer Add-on for Blender
# Copyright (C) 2019  Jens Neitzel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
    "name": "PBR Material Importer",
    "description": "Import Principled BSDF / PBR based materials from xml descriptions",
    "author": "Jens Neitzel",
    "version": (1, 3),
    "blender": (2, 80, 0),
    "location": "File > Import > PBR Material Description (.xml)",
    "url": "https://github.com/jensnt/pbr-material-importer",
    "wiki_url": "https://github.com/jensnt/pbr-material-importer",
    "tracker_url": "https://github.com/jensnt/pbr-material-importer/issues",
    "warning": "",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

import bpy
import os
import xml.etree.ElementTree as etree
import math
import re

class pbrMaterial():
    _SUPPORTED_PROPS = ["Base_Color", "Subsurface", "Subsurface_Radius", "Subsurface_Color", "Metallic", "Specular", "Specular_Tint", "Roughness", "Anisotropic", "Anisotropic_Rotation", "Sheen", "Sheen_Tint", "Clearcoat", "Clearcoat_Roughness", "IOR", "Transmission", "Normal", "Clearcoat_Normal", "Tangent", "Emission", "Opacity", "Displacement", "Bump"]
    _NON_STANDARD_PROPS   = ["Normal", "Clearcoat_Normal", "Tangent", "Emission", "Opacity", "Displacement", "Bump"]

    _DICT_PROP_PBR_NODE_INPUT = {"Base_Color"           : "Base Color",
                                 "Subsurface"           : "Subsurface",
                                 "Subsurface_Radius"    : "Subsurface Radius",
                                 "Subsurface_Color"     : "Subsurface Color",
                                 "Metallic"             : "Metallic",
                                 "Specular"             : "Specular",
                                 "Specular_Tint"        : "Specular Tint",
                                 "Roughness"            : "Roughness",
                                 "Anisotropic"          : "Anisotropic",
                                 "Anisotropic_Rotation" : "Anisotropic Rotation",
                                 "Sheen"                : "Sheen",
                                 "Sheen_Tint"           : "Sheen Tint",
                                 "Clearcoat"            : "Clearcoat",
                                 "Clearcoat_Roughness"  : "Clearcoat Roughness",
                                 "IOR"                  : "IOR",
                                 "Transmission"         : "Transmission",
                                 "Normal"               : "Normal",
                                 "Bump"                 : "Normal",
                                 "Clearcoat_Normal"     : "Clearcoat Normal",
                                 "Tangent"              : "Tangent"}

    def __init__(self, xmlMat, filepath, replace_existing):
        self.xmlMat = xmlMat
        self.xmlFilepath = filepath
        self.mat = None
        if replace_existing == True:
            for existingMat in bpy.data.materials:
                if existingMat.name == self.xmlMat.get('name'):
                    print("Replacing Material: %s" % (existingMat.name))
                    self.mat = existingMat
                    break
        if self.mat == None:
            print("Creating Material: %s" % (self.xmlMat.get('name')))
            self.mat = bpy.data.materials.new(name=self.xmlMat.get('name'))
        self.mat.use_nodes = True
        
        ## Remove all nodes in the materials node tree
        for node in self.mat.node_tree.nodes:
            self.mat.node_tree.nodes.remove(node)
        
        ## Create and connect basic nodes
        self.nodePbr = self.mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        self.nodePbr.location = (700,560)
        self.nodeMatOut = self.mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        self.nodeMatOut.location = (1000,560)
        self.mat.node_tree.links.new(self.nodePbr.outputs["BSDF"], self.nodeMatOut.inputs["Surface"])
        self.nodeEmissionAdd = None
        
        ## Create Image nodes
        self.imgNodes = []
        for prop in self._SUPPORTED_PROPS:
            matProperty = self.xmlMat.find(prop)
            if (matProperty != None):
                imgPath = self._getImgPathOfProp(matProperty)
                if (imgPath != None) and (self._getImgNodeMatchingProp(matProperty) == None):
                    self.imgNodes.append(nodeTexImage(self.xmlFilepath, self.mat, matProperty.find('Image')))
                    print(self.imgNodes[-1].imgTexNodeObj.image)
                    self.imgNodes[-1].imgTexNodeObj.image.colorspace_settings.name = self._getDefaultColorSpace(prop)
        for i in range(0, len(self.imgNodes)):
            self.imgNodes[i].setLocation((0,(-300*i)+(len(self.imgNodes)*300/2)+300))
            
        for prop in self._SUPPORTED_PROPS:
            matProperty = self.xmlMat.find(prop)
            if (matProperty != None):
                self._setupProperty(matProperty)
    
    def _addNormalMapNode(self, xmlProp, nodePropImg):
        nodeNormalMap = self.mat.node_tree.nodes.new(type='ShaderNodeNormalMap')
        nodeNormalMap.location = (250,nodePropImg.location[1])
        self.mat.node_tree.links.new(nodePropImg.outputs["Color"], nodeNormalMap.inputs["Color"])
        self.mat.node_tree.links.new(nodeNormalMap.outputs["Normal"], self.nodePbr.inputs[self._DICT_PROP_PBR_NODE_INPUT[xmlProp.tag]])
    
    def _addBumpMapNode(self, xmlProp, nodePropImg):
        nodeBumpMap = self.mat.node_tree.nodes.new(type='ShaderNodeBump')
        nodeBumpMap.location = (250,nodePropImg.location[1])
        self.mat.node_tree.links.new(nodePropImg.outputs["Color"], nodeBumpMap.inputs["Height"])
        self.mat.node_tree.links.new(nodeBumpMap.outputs["Normal"], self.nodePbr.inputs[self._DICT_PROP_PBR_NODE_INPUT[xmlProp.tag]])
    
    def _addEmissionNodes(self, xmlProp, nodePropImg):
        self.nodeEmissionAdd = self.mat.node_tree.nodes.new(type='ShaderNodeAddShader')
        self.nodeEmissionAdd.location = (1000,560)
        self.nodeEmission = self.mat.node_tree.nodes.new(type='ShaderNodeEmission')
        self.nodeEmission.location = (700,0)
        self.nodeMatOut.location = (1300,560)  ## Move Output Node more to the right.
        if self._hasAllowedAttributeDefaultValue(xmlProp):
            self.nodeEmission.inputs["Color"].default_value = eval(xmlProp.get('value'))
        if nodePropImg != None:
            self.mat.node_tree.links.new(nodePropImg.outputs["Color"], self.nodeEmission.inputs["Color"])
        if xmlProp.get('strength') != None:
            self.nodeEmission.inputs["Strength"].default_value = eval(xmlProp.get('strength'))
        self.mat.node_tree.links.new(self.nodeEmission.outputs["Emission"], self.nodeEmissionAdd.inputs[1])
        self.mat.node_tree.links.new(self.nodePbr.outputs["BSDF"], self.nodeEmissionAdd.inputs[0])
        self.mat.node_tree.links.new(self.nodeEmissionAdd.outputs["Shader"], self.nodeMatOut.inputs["Surface"])
    
    def _addOpacityNodes(self, xmlProp, nodePropImg):
        self.nodeOpacityMix = self.mat.node_tree.nodes.new(type='ShaderNodeMixShader')
        self.nodeOpacityMix.location = (1300,560)
        self.nodeTransparent = self.mat.node_tree.nodes.new(type='ShaderNodeBsdfTransparent')
        self.nodeTransparent.location = (1000,660)
        self.nodeMatOut.location = (1600,560)  ## Move Output Node more to the right.
        if self._hasAllowedAttributeDefaultValue(xmlProp):
            self.nodeOpacityMix.inputs[0].default_value = eval(xmlProp.get('value'))
        if nodePropImg != None:
            self.nodeOpacityInvert = self.mat.node_tree.nodes.new(type='ShaderNodeInvert')
            self.nodeOpacityInvert.location = (700,-140)
            self.nodeOpacityInvert.inputs[0].default_value = 0
            self.mat.node_tree.links.new(nodePropImg.outputs["Color"], self.nodeOpacityInvert.inputs["Color"])
            self.mat.node_tree.links.new(self.nodeOpacityInvert.outputs["Color"], self.nodeOpacityMix.inputs[0])
        if self.nodeEmissionAdd != None:
            self.mat.node_tree.links.new(self.nodeEmissionAdd.outputs["Shader"], self.nodeOpacityMix.inputs[2])
        else:
            self.mat.node_tree.links.new(self.nodePbr.outputs["BSDF"], self.nodeOpacityMix.inputs[2])
        self.mat.node_tree.links.new(self.nodeTransparent.outputs["BSDF"], self.nodeOpacityMix.inputs[1])
        self.mat.node_tree.links.new(self.nodeOpacityMix.outputs["Shader"], self.nodeMatOut.inputs["Surface"])
    
    def _addTangentNodes(self, xmlProp):
        xmlTangentNode = xmlProp.find('TangentNode')
        if xmlTangentNode != None:
            self.nodeTangent = self.mat.node_tree.nodes.new(type='ShaderNodeTangent')
            self.nodeTangent.location = (0, self.imgNodes[-1].imgTexNodeObj.location[1] - 300)
            self.mat.node_tree.links.new(self.nodeTangent.outputs["Tangent"], self.nodePbr.inputs["Tangent"])
            if xmlTangentNode.get('axis') != None:
                self.nodeTangent.axis = xmlTangentNode.get('axis')
            if xmlTangentNode.get('direction_type') != None:
                self.nodeTangent.direction_type = xmlTangentNode.get('direction_type')
            if xmlTangentNode.get('uv_map') != None:
                self.nodeTangent.uv_map = xmlTangentNode.get('uv_map')
        
    def _setupProperty(self, xmlProp):
        if self._isSupportedProp(xmlProp):
            print("Creating property for {}".format(str(xmlProp)))
            if self._hasAllowedAttributeImage(xmlProp):
                nodePropImg = self._getImgNodeMatchingProp(xmlProp).imgTexNodeObj
                if self._isNormalProp(xmlProp):
                    self._addNormalMapNode(xmlProp, nodePropImg)
                if self._isBumpProp(xmlProp):
                    self._addBumpMapNode(xmlProp, nodePropImg)
                if self._isEmissionProp(xmlProp):
                    self._addEmissionNodes(xmlProp, nodePropImg)
                if self._isOpacityProp(xmlProp):
                    self._addOpacityNodes(xmlProp, nodePropImg)
                if self._isDisplacementProp(xmlProp):
                    self.mat.node_tree.links.new(nodePropImg.outputs["Color"], self.nodeMatOut.inputs["Displacement"])
                    self.mat.cycles.displacement_method = 'BOTH'
                if self._isStandardProp(xmlProp):
                    self.mat.node_tree.links.new(nodePropImg.outputs["Color"], self.nodePbr.inputs[self._DICT_PROP_PBR_NODE_INPUT[xmlProp.tag]])
            elif self._hasAllowedAttributeDefaultValue(xmlProp):
                if self._isEmissionProp(xmlProp):
                    self._addEmissionNodes(xmlProp, None)
                if self._isOpacityProp(xmlProp):
                    self._addOpacityNodes(xmlProp, None)
                if self._isStandardProp(xmlProp):
                    self.nodePbr.inputs[self._DICT_PROP_PBR_NODE_INPUT[xmlProp.tag]].default_value = eval(xmlProp.get('value'))
            elif self._isTangentProp(xmlProp):
                self._addTangentNodes(xmlProp)
            else:
                print("Property \"%s\" found in material \"%s\" has no allowed attribute!" % (xmlProp.tag, self.xmlMat.tag))
        else:
            print("Unsupported Property \"%s\" found in material \"%s\"!" % (xmlProp.tag, self.xmlMat.tag))
    
    def _getImgPathOfProp(self, xmlProp):
        if self._hasAllowedAttributeImage(xmlProp):
            return os.path.normpath(os.path.join(os.path.dirname(self.xmlFilepath), xmlProp.find('Image').get('path')))
        else:
            return None
    
    def _getImgNodeMatchingProp(self, xmlProp):
        return next((x for x in self.imgNodes if self._matchImgNodeProp(x,xmlProp)), None)
    
    def _matchImgNodeProp(self, imgNode, xmlProp):
        propColorSpace = self._getDefaultColorSpace(xmlProp.tag)
        return (imgNode.imagePath == self._getImgPathOfProp(xmlProp)) and (imgNode.imgTexNodeObj.image.colorspace_settings.name == propColorSpace)
    
    def _isSupportedProp(self, xmlProp):
        return (xmlProp.tag in self._SUPPORTED_PROPS)

    def _isStandardProp(self, xmlProp):
        return self._isSupportedProp(xmlProp) and (xmlProp.tag not in self._NON_STANDARD_PROPS)

    def _isNormalProp(self, xmlProp):
        return (xmlProp.tag == "Normal") or (xmlProp.tag == "Clearcoat_Normal")

    def _isTangentProp(self, xmlProp):
        return (xmlProp.tag == "Tangent")

    def _isEmissionProp(self, xmlProp):
        return (xmlProp.tag == "Emission")

    def _isOpacityProp(self, xmlProp):
        return (xmlProp.tag == "Opacity")

    def _isDisplacementProp(self, xmlProp):
        return (xmlProp.tag == "Displacement")

    def _isBumpProp(self, xmlProp):
        return (xmlProp.tag == "Bump")

    def _isImgAllowedProp(self, xmlProp):
        return self._isSupportedProp(xmlProp) and (xmlProp.tag != "Tangent")

    def _isValueAllowedProp(self, xmlProp):
        return (self._isSupportedProp(xmlProp) and (xmlProp.tag != "Normal") and (xmlProp.tag != "Clearcoat_Normal")
                                               and (xmlProp.tag != "Tangent") and (xmlProp.tag != "Displacement"))
    
    def _hasAllowedAttributeImage(self, xmlProp):
        propImage = xmlProp.find('Image')
        if propImage != None:
            return self._isImgAllowedProp(xmlProp) and (propImage.get('path') != None)
    
    def _hasAllowedAttributeDefaultValue(self, xmlProp):
        return (self._isValueAllowedProp(xmlProp) and xmlProp.get('value') != None)
    
    def _getDefaultColorSpace(self, prop):
        if (prop == "Base_Color") or (prop == "Subsurface_Color") or (prop == "Emission"):
            return 'sRGB'
        else:
            return 'Non-Color'

class nodeTexImage():
    def __init__(self, xmlFilepath, bpyMaterial, xmlImageElement):
        self.xmlFilepath = xmlFilepath
        self.mat = bpyMaterial
        self.imagePath = os.path.normpath(os.path.join(os.path.dirname(self.xmlFilepath), xmlImageElement.get('path')))
        self.imgTexNodeObj = self.mat.node_tree.nodes.new(type='ShaderNodeTexImage')
        self.imgTexNodeObj.image = bpy.data.images.load(self.imagePath)
        
        self.xmlMapping = xmlImageElement.find('Mapping')
        self.xmlTextureCoordinate = None
        self.mappingNodeObj = None
        self.texCoordNodeObj = None
        if self.xmlMapping != None:
            self.xmlTextureCoordinate = self.xmlMapping.find('TextureCoordinate')
        if self.xmlTextureCoordinate != None:
            texCoordOutput = self.xmlTextureCoordinate.get('output')
            if texCoordOutput == None:
                texCoordOutput = "UV"
            self.mappingNodeObj = self.mat.node_tree.nodes.new(type='ShaderNodeMapping')
            self.texCoordNodeObj = self.mat.node_tree.nodes.new(type='ShaderNodeTexCoord')
            self.mat.node_tree.links.new(self.texCoordNodeObj.outputs[texCoordOutput], self.mappingNodeObj.inputs["Vector"])
            self.mat.node_tree.links.new(self.mappingNodeObj.outputs["Vector"], self.imgTexNodeObj.inputs["Vector"])
            if self.xmlMapping.get('vector_type') != None:
                self.mappingNodeObj.vector_type = self.xmlMapping.get('vector_type')
            if self.xmlMapping.get('location') != None:
                self.mappingNodeObj.inputs['Location'].default_value = eval(self.xmlMapping.get('location'))
            if self.xmlMapping.get('rotation') != None:
                rotX = math.radians(eval(self.xmlMapping.get('rotation'))[0])
                rotY = math.radians(eval(self.xmlMapping.get('rotation'))[1])
                rotZ = math.radians(eval(self.xmlMapping.get('rotation'))[2])
                self.mappingNodeObj.inputs['Rotation'].default_value = (rotX,rotY,rotZ)
            if self.xmlMapping.get('scale') != None:
                self.mappingNodeObj.inputs['Scale'].default_value = eval(self.xmlMapping.get('scale'))
        
    def setLocation(self, location):
        self.imgTexNodeObj.location = location
        if self.mappingNodeObj != None:
            self.mappingNodeObj.location = (location[0]-420,location[1])
        if self.texCoordNodeObj != None:
            self.texCoordNodeObj.location = (location[0]-660,location[1])

class PBR_MATERIAL_IMPORTER_OT_import(bpy.types.Operator):
    """PBR Material Importer"""
    bl_idname = "pbr_material_importer.import"
    bl_label = "Import PBR Materials from XML"
    bl_options = {'REGISTER', 'UNDO'}
    
    _MIN_MAJOR_XML_VERSION = 1
    _MIN_MINOR_XML_VERSION = 0
    _MAX_MAJOR_XML_VERSION = 1
    _MAX_MINOR_XML_VERSION = 1
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.xml", options={'HIDDEN'})
    replace_existing: bpy.props.BoolProperty(name="Replace existing Materials",
                                             description="Existing Materials with the same name as the imported ones will be replaced",
                                             default=False)
    
    def execute(self, context):
        # Create new materials from XML file
        print("Importing from file: %s" % (self.filepath))
        pbrMaterials = []
        root = etree.parse(self.filepath).getroot()
        if self._isSupportedVersion(root.get('version')):
            for elemMaterial in root.findall('Material'):
                pbrMaterials.append(pbrMaterial(elemMaterial, self.filepath, self.replace_existing))
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def _isSupportedVersion(self, version):
        if (version != None):
            match = re.match("^([0-9]+)\.([0-9]+)$", version)
            if (match != None):
                major = int(match.group(1))
                minor = int(match.group(2))
                if ((major >= self._MIN_MAJOR_XML_VERSION) and (major <= self._MAX_MAJOR_XML_VERSION) and
                    (minor >= self._MIN_MINOR_XML_VERSION) and (minor <= self._MAX_MINOR_XML_VERSION)):
                    return True
        print("XML has unsupported version: \"%s\"\nSupported Versions are: %s.%s to %s.%s" % (version,
        self._MIN_MAJOR_XML_VERSION, self._MIN_MINOR_XML_VERSION, self._MAX_MAJOR_XML_VERSION, self._MAX_MINOR_XML_VERSION))
        return False

def menu_import(self, context):
    self.layout.operator(PBR_MATERIAL_IMPORTER_OT_import.bl_idname, text="PBR Material Description (.xml)")

def register():
    bpy.utils.register_class(PBR_MATERIAL_IMPORTER_OT_import)
    # Add import menu item
    if hasattr(bpy.types, 'TOPBAR_MT_file_import'):
        #2.8+
        bpy.types.TOPBAR_MT_file_import.append(menu_import)
    else:
        bpy.types.INFO_MT_file_import.append(menu_import)

def unregister():
    bpy.utils.unregister_class(PBR_MATERIAL_IMPORTER_OT_import)
    # Remove import menu item
    if hasattr(bpy.types, 'TOPBAR_MT_file_import'):
        #2.8+
        bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    else:
        bpy.types.INFO_MT_file_import.remove(menu_import)

if __name__ == "__main__":
    register()
