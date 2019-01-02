# PBR Material Importer for Blender
This Add-on lets you import materials from XML descriptions.  
It will create node trees for those materials based around the [Principled BSDF node](https://docs.blender.org/manual/en/dev/render/cycles/nodes/types/shaders/principled.html).

![Nodes](/images/nodes.png)

## Installation

To install the Add-on you need [Blender](https://www.blender.org/) in version 2.79 or later.

1. Download the Add-on file: [pbr-material-importer.py](https://raw.githubusercontent.com/jensnt/pbr-material-importer/master/pbr-material-importer.py)
2. Install the Add-on by opening the Blender User Preferences and clicking on "Install Add-on from File…" at the bottom of the "Add-ons" tab to provide the file.
3. The Add-on will not be enabled automatically. You have to enable it by checking it's check box in the Add-on list before you can use it.
4. If you want the Add-on enabled by default every time you start Blender, click on the "Save User Settings" button at the bottom of the "Add-ons" tab.

## Replacing materials

When importing materials with the same name as already existing ones in your project, a number will be added as a suffix to the imported material names by default.

If instead you want to replace existing materials with the same name, you have the option to check the "Replace existing Materials" check box in the importer dialog:

![Replace existing Materials](/images/replace-existing-materials.png)

## Creating Material Description XML files

The basic structure you need to create looks like this:

```
<?xml version="1.0"?>
<PbrMaterialDescriptions version="1.1">
    <Material name="My Material"/>
</PbrMaterialDescriptions>
```

The following properties can be defined as child elements for materials:

* ```Base_Color```
* ```Subsurface```
* ```Subsurface_Radius```
* ```Subsurface_Color```
* ```Metallic```
* ```Specular```
* ```Specular_Tint```
* ```Roughness```
* ```Anisotropic```
* ```Anisotropic_Rotation```
* ```Sheen```
* ```Sheen_Tint```
* ```Clearcoat```
* ```Clearcoat_Roughness```
* ```IOR```
* ```Transmission```
* ```Normal```
* ```Bump```
* ```Clearcoat_Normal```
* ```Tangent```
* ```Emission```
* ```Opacity```
* ```Displacement```

For those properties supporting it:

A value for a property can be defined by adding it as an attribute to the property element:  
```<Base_Color value="(0.72, 0.22, 0.09)"/>```

To define an Image Texture Node as input for a property, an "Image" child element can be added to the property element including a "path" attribute pointing to the texture file:  
```<Image path="./Bricks05/Bricks05_col.jpg"/>```  
The path must be relative to the XML file or absolute.

For more options and details please refer to the Schema Definition:
[PbrMaterialDescriptions.xsd](/PbrMaterialDescriptions.xsd)

You can find an interactive visual representation of the schema [here](http://visualxsd.com/Home/LoadSavedSchema/f0eebb834eb31c9a6feac3d12fe925327d681076) on visualxsd.com.
