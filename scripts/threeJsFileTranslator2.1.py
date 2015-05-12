# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

__author__ = 'Justin Herbst'
__version__ = '0.2.0'
__email__ = 'justin@justifiedvisual.com'

#----
#TODO



import sys
import json
from decimal import *
import maya.cmds as mc
import maya.OpenMayaAnim as omAnim
from maya.OpenMaya import *
from maya.OpenMayaMPx import *

kPluginTranslatorTypeName = 'Three.js2'
kOptionScript = 'ThreeJsExportScript2'
kDefaultOptionsString = '0'


# #####################################################
# Global Vars
# #####################################################

# skinning
MAX_INFLUENCES = 2 #can be 2 or 4



# #####################################################
# JSON Encoder
# #####################################################

class ComplexEncoder(json.JSONEncoder):
	def _iterencode(self, o, markers=None):
		if isinstance(o, float):
			s = str(o)
			if '.' in s:
				s = "%.8f" % o
				while '.' in s and s[-1] == '0':
					s = s[-2]
			return (s for s in [s])
		return super(DecimalEncoder, self)._iterencode(o, markers)
	def default(self, obj):
		if hasattr(obj,'reprJSON'):
			return obj.reprJSON()
		else:
			return json.JSONEncoder.default(self, obj)


# #####################################################
# Classes
# #####################################################

#class Defining the Animation object
class Animation:
	def __init__(self):
		self.name = ""
		self.fps = 30
		self.length = 0
		self.JIT = 0
		self.hierarchy = []
	def __repr__(self):
		return  repr((self.__dict__))
	def reprJSON(self):
		return dict(name=self.name, fps=self.fps, length=self.length, JIT=self.JIT, hierarchy=self.hierarchy)
		
#class Defining the Animated Joint object
class AnimatedObject:
	def __init__(self):
		self.parent = -1
		self.keys = []
	def __repr__(self):
		return repr((self.__dict__))
	def reprJSON(self):
		return dict(parent=self.parent, keys=self.keys)
		
#class Defining the KeyFrame object
class KeyFrame:
	def __init__(self):
		self.time = -1
		self.pos = []
		self.rot = []
		self.scl = []
	def __repr__(self):
		return repr((self.__dict__))
	def reprJSON(self):
		return dict(time=self.time, pos=self.pos, rot=self.rot, scl=self.scl)
		
#class Defining the Joint object
class NewJoint:
	def __init__(self, thisParent=-1, name="", pos=[0,0,0], scl=[1,1,1], rotq=[0,0,0,1]):
		self.parent = thisParent
		self.name = name
		self.pos = pos
		self.scl = scl
		self.rotq = rotq
	def __repr__(self):
		return  repr((self.__dict__))
	def reprJSON(self):
		return dict(parent=self.parent, name=self.name, pos=self.pos, scl=self.scl, rotq=self.rotq)
		
#class Defining the object to keep the Influence weight and joint index
class VertInfluence:
	def __init__(self, weight, jointIndex ):
		self.weight = weight
		self.jointIndex = jointIndex
	def __repr__(self):
		return repr((self.__dict__))
		
#class to round to 8 decimal places
def _round8(floatIn ):
		return float('{0:.8f}'.format(floatIn))
		
#Error Class
class ThreeJsError(Exception):
	pass
	
	
# #####################################################
# Main Program
# #####################################################

class ThreeJsWriter(object):
	def __init__(self):
		self.componentKeys = ['vertices', 'normals', 'colors', 'uvs', 'materials', 'faces', 'bones', 'skinIndices', 'skinWeights', 'animation']
		
	def _parseOptions(self, optionsString):
		self.options = dict([(x, False) for x in self.componentKeys])
		self.options['animationName'] = ''
		optionsString = optionsString[2:] # trim off the '0;' that Maya adds to the options string
		for option in optionsString.split(' '):
			if 'animationName:' in option:
				self.options['animationName'] = option.split(':')[1]
			else:
				self.options[option] = True
		
			
	def _updateOffsets(self):
		for key in self.componentKeys:
			if key == 'uvs' or 'vertices':
				continue
			self.offsets[key] = len(getattr(self, key))
		for i in range(len(self.uvs)):
			self.offsets['uvs'][i] = len(self.uvs[i])/2
		self.offsets['vertices'] = len(self.vertices)/3
		self.offsets['normals'] = len(self.normals)/3
		self.offsets['colors'] = len(self.normals)/3
		
	def _getTypeBitmask(self, options):
		bitmask = 0
		if options['materials']:
			bitmask |= 2
		if options['uvs']:
			bitmask |= 8
		if options['normals']:
			bitmask |= 32
		if options['colors']:
			bitmask |= 128
		return bitmask
		
	def _exportMesh(self, dagPath, component, meshName):
		mesh = MFnMesh(dagPath)
		options = self.options.copy()
		self.currentMeshName = meshName
		self._updateOffsets()
		# export vertex data
		if options['vertices']:
			try:
				iterVerts = MItMeshVertex(dagPath, component)
				while not iterVerts.isDone():
					point = iterVerts.position(MSpace.kWorld)
					self.vertices += [_round8(point.x), _round8(point.y), _round8(point.z)]
					iterVerts.next()
			except:
				options['vertices'] = False
				print 'ERROR: Could not export Face Vertices!'
				

		# export uv data
		if options['uvs']:
			try:
				uvLayers = []
				mesh.getUVSetNames(uvLayers)
				while len(uvLayers) > len(self.uvs):
					self.uvs.append([])
					self.offsets['uvs'].append(0)
				for i, layer in enumerate(uvLayers):
					uList = MFloatArray()
					vList = MFloatArray()
					mesh.getUVs(uList, vList, layer)
					for j in xrange(uList.length()):
						self.uvs[i] += [_round8(uList[j]), _round8(vList[j])]
			except:
				options['uvs'] = False
				print 'ERROR: Could not export UVs!'
				
		# export normal data
		if options['normals']:
			try:
				normals = MFloatVectorArray()
				mesh.getNormals(normals, MSpace.kWorld)
				for i in xrange(normals.length()):
					point = normals[i]
					self.normals += [_round8(point.x), _round8(point.y), _round8(point.z)]
			except:
				options['normals'] = False
				print 'ERROR: Could not export Normals!'
				
		# export color data
		if options['colors']:
			try:
				colors = MColorArray()
				mesh.getColors(colors)
				for i in xrange(colors.length()):
					color = colors[i]
					# uncolored vertices are set to (-1, -1, -1).  Clamps colors to (0, 0, 0).
					self.colors += [max(color.r, 0), max(color.g, 0), max(color.b, 0)]
			except:
				options['colors'] = False
				print 'ERROR: Could not export Normals!'
				
		# export face data
		if options['vertices']:
			#try:
			bitmask = self._getTypeBitmask(options)
			iterPolys = MItMeshPolygon(dagPath, component)
			currentPoly = 0
			while not iterPolys.isDone():
				
				# export face vertices
				verts = MIntArray()
				iterPolys.getVertices(verts)
				if verts.length() == 3:
					self.faces.append(bitmask)
				elif verts.length() == 4:
					self.faces.append(bitmask + 1)
				else:
					print 'ERROR: One or more of your faces have more than 4 sides! Please Triangulate your Mesh and try Again.'
					raise ThreeJsError(('ERROR: One or more of your faces have more than 4 sides!!' + meshName + '[' + str(currentPoly) + ']. Please Triangulate your Mesh and try Again: {0}').format(self.accessMode))
					
				for i in xrange(verts.length()):
					self.faces.append(verts[i] + self.offsets['vertices'])
				# export face vertex materials
				if options['materials']:
					materialIndex = 0
					meshTransform = mc.listRelatives(meshName, parent=True, fullPath=True)
					face = str(meshTransform[0]) + '.f['+str(iterPolys.index())+']'
					#print face
					sgs = mc.listSets(t=1, o=face)
					if sgs != None:
						material = mc.ls(mc.listConnections(sgs[0]),materials=1) 
						if len(material):
							for i in xrange(len(self.materials)):
								
								if self.materials[i]['DbgName'] == material[0]:
									materialIndex = i
									#print face + ' has material ' + str(material[0]) + ' index: ' + str(i)
						self.faces.append(materialIndex)
					
				#self.faces.append(len(self.materials))
				# export face vertex uvs
				if options['uvs']:
					util = MScriptUtil()
					uvPtr = util.asIntPtr()
					for i, layer in enumerate(uvLayers):
						for j in xrange(verts.length()):
							iterPolys.getUVIndex(j, uvPtr, layer)
							uvIndex = util.getInt(uvPtr)
							self.faces.append(uvIndex + self.offsets['uvs'][i])
				# export face vertex normals
				if options['normals']:
					for i in xrange(verts.length()):
						normalIndex = iterPolys.normalIndex(i)
						self.faces.append(normalIndex + self.offsets['normals'])
				# export face vertex colors
				if options['colors']:
					colors = MIntArray()
					iterPolys.getColorIndices(colors)
					for i in xrange(colors.length()):
						self.faces.append(colors[i] + self.offsets['colors'])
				
				currentPoly += 1
				iterPolys.next()
			'''
			except:
				options['vertices'] = False
				print 'ERROR: Could not export Face Vertices!'
			'''	
	def _exportBones(self, mesh, dagPath):
		options = self.options.copy()
		if options['bones']:
			# export skeleton skinIndices skinWeights and animation
			
			for skin in self.skins:
				skinMeshes = mc.skinCluster(skin, q=1, g=1)
				if mesh in skinMeshes:
					selectionList = MSelectionList()
					selectionList.add( skin )
					node = MObject()
					selectionList.getDependNode( 0, node )
					skinClusterNode = omAnim.MFnSkinCluster(node)
					infs = MDagPathArray()
					numInfs = skinClusterNode.influenceObjects(infs)
					skinPath = MDagPath()
					index = 0
					skinClusterNode.indexForOutputConnection(index)
					skinClusterNode.getPathAtIndex(index,skinPath)
					geom = MItGeometry(dagPath)
					vertecies = geom.count()
					inflNames = []
					for counter in range(0,numInfs,1):
						infName = infs[counter].partialPathName()
						inflNames.append(infName)
					firstJoint = inflNames[0]
					while mc.listRelatives(firstJoint, p=True):
						parent = mc.listRelatives(firstJoint, p=True)
						firstJoint = parent[0]
					if len(self.bones) == 0:
						self.saveJoints(firstJoint, -1)
					elif firstJoint != self.bones[0].name:
						self.saveJoints(firstJoint, -1)
					jointIndices = []
					for n in range(0,len(inflNames),1):
						for i in range(0,len(self.bones),1):
							if self.bones[i].name == inflNames[n]:
								jointIndices.append(i)
					wts = MDoubleArray()
					infCount = MScriptUtil()
					ccc = infCount.asUintPtr()
					component = MObject()
					
					while  not geom.isDone():
						component = geom.component()
						skinClusterNode.getWeights(skinPath,component,wts,ccc)
						vertInfluences =[]
						vertWeightInfo=[]
						if len(jointIndices):
							for i in range(0,(len(wts)/ len(jointIndices)),1):
								vertInfluences = []
								for n in range(0, len(jointIndices),1):
									jointIndex = jointIndices[n]
									vertInfluences.append( VertInfluence( wts[n], jointIndex ) )
								vertInfluences = sorted( vertInfluences, key=lambda vertInfluence: vertInfluence.weight)
								vertInfluences.reverse()
								vertWeightTotal = 0
								for n in range(0,MAX_INFLUENCES,1):
									weight = _round8(vertInfluences[n].weight)
									#if this is the last influence the next influence will take the remainder.
									if n == MAX_INFLUENCES - 1 or vertInfluences[n+1].weight == 0:
										weight = vertInfluences[n].weight = 1 - vertWeightTotal
									vertWeightTotal += weight
									self.skinIndices.append(vertInfluences[n].jointIndex)
									self.skinWeights.append(float(weight))
									
									#DEBUG print 'component = ' + str(component) + ' index = ' + str(vertInfluences[n].jointIndex) + ' weight = ' + str(weight)
						geom.next()
	def _exportMaterials(self):
		options = self.options.copy()
		if options['materials']:
			
			sgs = mc.ls(type='shadingEngine')
			materials = []
			materialFaces = []
			for sg in sgs:
				children = mc.ls(mc.listConnections(sg),materials=1) 
				if len(children) and children[0] not in materials:
					materials.append(children[0])
			materials = list(set(materials))
			for material in materials:
				if mc.nodeType(material) == 'phong':
					#print 'PhongMaterial - ' + str(material)
					color = mc.getAttr(str(material) + '.color')
					ambColor = mc.getAttr(str(material) + '.ambientColor')
					diffuse = [color[0][0] * mc.getAttr(str(material) + '.diffuse'),color[0][1] * mc.getAttr(str(material) + '.diffuse'),color[0][2] * mc.getAttr(str(material) + '.diffuse')]
					specularColor = mc.getAttr(str(material) + '.specularColor')
					specularCoef = mc.getAttr(str(material) + '.cosinePower')
					transparencyVec = mc.getAttr(str(material) + '.transparency')
					opacity = (transparencyVec[0][0] + transparencyVec[0][1] + transparencyVec[0][2])/3
					imageMap = ''
					bumpMap = ''
					bumpScale = ''
					if mc.connectionInfo((material+'.color'), isDestination=1):
						listColorTextures = mc.listConnections(material+'.color')
						if str(mc.nodeType(listColorTextures[0])) == 'file':
							imageMap = mc.getAttr(listColorTextures[0]+'.fileTextureName')
					
					#if mc.connectionInfo((material+'.normalCamera'), isDestination=1):
					#	listColorTextures = mc.listConnections(material+'.normalCamera')
					#	if str(mc.nodeType(listColorTextures[0])) == 'file':
					#		bumpMap = mc.getAttr(listColorTextures[0]+'.fileTextureName')
						
					
					if opacity < 1:
						transparent = False
					else:
						transparent = True
						
					self.materials.append({
						"DbgName" : str(material),
				    	"blending" : "NormalBlending",
				    	"colorAmbient" : [ ambColor[0][0], ambColor[0][1], ambColor[0][2] ],
				    	"colorDiffuse" : [diffuse[0], diffuse[1], diffuse[2]],
				    	"colorSpecular" : [specularColor[0][0],specularColor[0][1],specularColor[0][2]],
				    	"depthTest" : True,
				    	"depthWrite" : True,
				    	"shading" : "Phong",
				    	"specularCoef" : specularCoef,
				    	"map": imageMap,
				    	#"bumpMap": bumpMap,
				    	#"bumpScale": bumpScale,
				    	"opacity" : opacity,
				    	"transparent" : transparent,
						"vertexColors" : False})
						
				elif mc.nodeType(material) == 'lambert':
					#print 'LambertMaterial - ' + str(material)
					color = mc.getAttr(str(material) + '.color')
					ambColor = mc.getAttr(str(material) + '.ambientColor')
					diffuse = [color[0][0] * mc.getAttr(str(material) + '.diffuse'),color[0][1] * mc.getAttr(str(material) + '.diffuse'),color[0][2] * mc.getAttr(str(material) + '.diffuse')]
					transparencyVec = mc.getAttr(str(material) + '.transparency')
					opacity = (transparencyVec[0][0] + transparencyVec[0][1] + transparencyVec[0][2])/3
					imageMap = ''
					bumpMap = ''
					bumpScale = ''
					if mc.connectionInfo((material+'.color'), isDestination=1):
						listColorTextures = mc.listConnections(material+'.color')
						if str(mc.nodeType(listColorTextures[0])) == 'file':
							imageMap = mc.getAttr(listColorTextures[0]+'.fileTextureName')
					
					#if mc.connectionInfo((material+'.normalCamera'), isDestination=1):
					#	listColorTextures = mc.listConnections(material+'.normalCamera')
					#	if str(mc.nodeType(listColorTextures[0])) == 'file':
					#		bumpMap = mc.getAttr(listColorTextures[0]+'.fileTextureName')
						
					
					if opacity < 1:
						transparent = False
					else:
						transparent = True
						
					self.materials.append({
						"DbgName" : str(material),
				    	"blending" : "NormalBlending",
				    	"colorAmbient" : [ ambColor[0][0], ambColor[0][1], ambColor[0][2] ],
				    	"colorDiffuse" : [diffuse[0], diffuse[1], diffuse[2]],
				    	"depthTest" : True,
				    	"depthWrite" : True,
				    	"shading" : "Lambert",
				    	"map": imageMap,
				    	#"bumpMap": bumpMap,
				    	#"bumpScale": bumpScale,
				    	"opacity" : opacity,
				    	"transparent" : transparent,
						"vertexColors" : False})
				else:
					#print 'OtherMaterial - ' + str(material)
					
					self.materials.append({
						"DbgName" : str(material),
					    "blending" : "NormalBlending",
					    "colorAmbient" : [0.5,0.5,0.5],
					    "colorDiffuse" :  [0.5,0.5,0.5],
					    "colorSpecular" : [0.9,0.9,0.9],
					    "depthTest" : True,
					    "depthWrite" : True,
					    "shading" : "Phong",
					    "specularCoef" : 100,
					    "vertexColors" : False})
										
	def _getMeshes(self, nodes):
		meshes = []
		for node in nodes:
			
			while mc.nodeType(node) != 'transform':
				node = mc.listRelatives(node, p=1)
			children = mc.listRelatives(node, typ='mesh',c=1, s=1)
			if children[0] not in meshes:
				meshes.append(children[0])
				
		return meshes
		
	def _exportMeshes(self):
		mc.currentTime(mc.playbackOptions(q=True, ast=True))
		
		# export all
		if self.accessMode == MPxFileTranslator.kExportAccessMode:
			meshes = self._getMeshes(mc.ls(typ='mesh'))
			
		# export selection
		elif self.accessMode == MPxFileTranslator.kExportActiveAccessMode:
			transformObjs = mc.ls(sl=1)
			if not len(transformObjs):
				print 'ERROR: Nothing Selected - please select an object and try again'
				raise ThreeJsError('ERROR: Nothing Selected: {0}'.format(self.accessMode))
			meshes = self._getMeshes(transformObjs)
		else:
			raise ThreeJsError('Unsupported access mode: {0}'.format(self.accessMode))
			
		for mesh in meshes:
			#print mesh
			mc.currentTime(mc.playbackOptions(q=True, ast=True))
			
			mc.polySelectConstraint(dis=True)
			mc.select(mesh)
			sel = MSelectionList()
			MGlobal.getActiveSelectionList(sel)
			mDag = MDagPath() 
			mComp = MObject()
			sel.getDagPath(0, mDag, mComp)
			self.gotoBindPose()
			self._exportMesh(mDag, mComp, mesh)
			self._exportBones(mesh,mDag)
			
	def gotoBindPose(self):
		try:
			joints = mc.ls(type='joint')
			topJoints = []
			for thisjoint in joints:
				while mc.listRelatives(thisjoint, p=True):
					parent = mc.listRelatives(thisjoint, p=True)
					thisjoint = parent[0]
				topJoints.append(thisjoint)
			topJoints = set(topJoints)
			for topJoint in topJoints:
				mc.select(topJoint)
				mypose = mc.dagPose( q=True, bindPose=True )
				mc.dagPose( mypose[0] , restore=True )	
				mc.select(cl=True)
		except:
			print 'cannot go to bind pose'
			
			
	#Saves the current joint in 'bones'
	def saveJoint(self, jointName, parentIndex):
		
		#print jointName
		thisJoint = NewJoint()
		mc.currentTime(mc.playbackOptions(q=True, ast=True))
		selList = MSelectionList() 
		selList.add(jointName)
		mc.select(jointName)
		mypose = mc.dagPose( q=True, bindPose=True )
		mc.dagPose( mypose[0] , restore=True )
		mDagPath = MDagPath() 
		selList.getDagPath(0, mDagPath)
		transformFunc = MFnTransform(mDagPath)
		mTransformMtx = transformFunc.transformation()
		jointRotq = mTransformMtx.rotation()
		jointRote = mTransformMtx.eulerRotation()
		scaleUtil = MScriptUtil()
		scaleUtil.createFromList([0,0,0],3)
		scaleVec = scaleUtil.asDoublePtr()
		mTransformMtx.getScale(scaleVec,MSpace.kWorld)
		jointScale = [_round8(MScriptUtil.getDoubleArrayItem(scaleVec,i)) for i in range(0,3)]
		absJointPos = mc.xform(jointName,q=1,ws=1,rp=1)
		if parentIndex != -1:
			parentJointPos = mc.xform(self.bones[parentIndex].name,q=1,ws=1,rp=1)
		else:
			parentJointPos = [0,0,0]
		jointPos = [absJointPos[0]-parentJointPos[0],absJointPos[1]-parentJointPos[1],absJointPos[2]-parentJointPos[2]]
		thisJoint.parent = parentIndex
		thisJoint.name = jointName
		thisJoint.pos = [_round8(jointPos[0]),_round8(jointPos[1]),_round8(jointPos[2])]
		thisJoint.scl = jointScale
		thisJoint.rotq = [_round8(jointRotq.x), _round8(jointRotq.y), _round8(jointRotq.z), _round8(jointRotq.w)]
		thisJoint.rot = [_round8(jointRote.x), _round8(jointRote.y), _round8(jointRote.z)]
		#print thisJoint.pos
		self.bones.append(thisJoint)
		
	#Saves the Animation for the current joint
	def saveAnimation(self, jointName, parentIndex):
		currentJoint = AnimatedObject()
		currentJoint.parent = parentIndex
		startFrame = mc.playbackOptions(q=True, ast=True)
		endFrame = mc.playbackOptions(q=True, aet=True)
		mc.currentTime(mc.playbackOptions(q=True, ast=True))
		originalPos = [mc.getAttr(jointName+'.translateX'), mc.getAttr(jointName+'.translateY'), mc.getAttr(jointName+'.translateZ')]
		
		if mc.keyframe(jointName, q=True):
			keyTimes = list(set(mc.keyframe(jointName, q=True)))
		else: 
			keyTimes = []
		keyTimes.sort()
		if len(keyTimes) == 0 or keyTimes[0] != startFrame:
			keyTimes.insert(0,startFrame)
		if keyTimes[len(keyTimes)-1] != endFrame:
			keyTimes.append(endFrame)
		for thisTime in keyTimes:
			if thisTime <= endFrame:
				mc.currentTime(thisTime)
				selList = MSelectionList() 
				selList.add(jointName)
				mDagPath = MDagPath() 
				selList.getDagPath(0, mDagPath)
				scaleUtil = MScriptUtil()
				scaleUtil.createFromList([0,0,0],3)
				scaleVec = scaleUtil.asDoublePtr()
				transformFunc = MFnTransform(mDagPath)
				mTransformMtx = transformFunc.transformation()
				mTransformMtx.getScale(scaleVec,MSpace.kWorld)
				jointScale = [_round8(MScriptUtil.getDoubleArrayItem(scaleVec,i)) for i in range(0,3)]
				absJointPos = [mc.getAttr(jointName+'.translateX'), mc.getAttr(jointName+'.translateY'), mc.getAttr(jointName+'.translateZ')]
				
				if parentIndex == -1:
					jointPos = [absJointPos[0], absJointPos[1], absJointPos[2]]
				else:
					jointPos = [(absJointPos[0]-originalPos[0] + self.bones[-1].pos[0]),(absJointPos[1]-originalPos[1] + self.bones[-1].pos[1] ),(absJointPos[2]-originalPos[2] + self.bones[-1].pos[2] )]
				jointRot = mTransformMtx.rotation()
				thisKey = KeyFrame()
				thisKey.time = _round8((thisTime - startFrame)/self.animation.fps)
				thisKey.pos = [_round8(jointPos[0] ),_round8(jointPos[1]),_round8(jointPos[2])]
				#thisKey.pos = self.bones[-1].pos
				#print thisKey.pos 
				thisKey.scl = jointScale
				thisKey.rot = [_round8(jointRot.x), _round8(jointRot.y), _round8(jointRot.z), _round8(jointRot.w)]
				currentJoint.keys.append(thisKey)
				
		self.animation.hierarchy.append(currentJoint)
		
	#Function to save joints takes the first joint and iterates through the hierarchy
	def saveJoints(self, jointCurrent, parentIndex):
		thisIndex = len(self.bones)
		if self.options['bones']:
			self.saveJoint(jointCurrent, parentIndex)
		if self.options['animation']:
			self.saveAnimation(jointCurrent, parentIndex)
			
		#iterate through hierachy
		if mc.listRelatives(jointCurrent, children=True):
			parentIndex+=1
			for nextJoint in mc.listRelatives(jointCurrent, children=True):
				self.saveJoints(nextJoint, thisIndex)
				
	#the main definition of the main program
	def write(self, path, optionString, accessMode):
		self.path = path
		self._parseOptions(optionString)
		self.accessMode = accessMode
		self.root = dict(metadata=dict(formatVersion=3.1))
		self.offsets = dict()
		for key in self.componentKeys:
			setattr(self, key, [])
			self.offsets[key] = 0
		self.offsets['uvs'] = []
		self.uvs = []
		self.materials = []
		self.skinWeights = []
		self.bones = []
		self.animation = Animation()
		self.animation.name = 'animation1'
		if self.options['animationName'] != '':
			self.animation.name = self.options['animationName']
		self.animation.fps = 30
		self.animation.length = _round8((mc.playbackOptions(q=True, aet=True) - mc.playbackOptions(q=True, ast=True))/self.animation.fps)
		self.skins = mc.ls(type='skinCluster')
		self.skinIndices = []
		self._exportMaterials()
		self._exportMeshes()
		# add the component buffers to the root JSON object
		for key in self.componentKeys:
			buffer_ = getattr(self, key)
			if buffer_:
				
				self.root[key] = buffer_
				
		# materials are required for parsing
		if not self.root.has_key('materials'):
			self.root['materials'] = [{}]
			
		# write the file
		with file(self.path, 'w') as f:
			f.write(json.dumps(self.root, separators=(',',':'), cls=ComplexEncoder))
			
			
			
# #####################################################
# Translator
# #####################################################

class ThreeJsTranslator(MPxFileTranslator):
	def __init__(self):
		MPxFileTranslator.__init__(self)
		
	def haveWriteMethod(self):
		return True
		
	def filter(self):
		return '*.js'
		
	def defaultExtension(self):
		return 'js'
		
	def writer(self, fileObject, optionString, accessMode):
		#print fileObject
		path = fileObject.fullName()
		writer = ThreeJsWriter()
		writer.write(path, optionString, accessMode)
		
		
def translatorCreator():
	return asMPxPtr(ThreeJsTranslator())
	
	
# #####################################################
# Plugin
# #####################################################


def initializePlugin(mobject):
	mplugin = MFnPlugin(mobject)
	try:
		mplugin.registerFileTranslator(kPluginTranslatorTypeName, None, translatorCreator, kOptionScript, kDefaultOptionsString)
	except:
		sys.stderr.write('Failed to register translator: %s' % kPluginTranslatorTypeName)
		raise
		
		
def uninitializePlugin(mobject):
	mplugin = MFnPlugin(mobject)
	try:
		mplugin.deregisterFileTranslator(kPluginTranslatorTypeName)
	except:
		sys.stderr.write('Failed to deregister translator: %s' % kPluginTranslatorTypeName)
		raise