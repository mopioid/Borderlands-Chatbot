from unrealsdk import *
from Mods import ModMenu
import os
import json


OutputDirectory = os.path.expandvars("%APPDATA%\\BorderlandsLiveFeed")
OutputPath = os.path.join(OutputDirectory, "Output.json")

def _SaveOutput():
	if not os.path.exists(OutputDirectory):
		os.makedirs(OutputDirectory)
	with open(OutputPath, "w") as outputFile:
		json.dump(Output, outputFile, indent=4)


_HeadClass = FindClass("CustomizationType_Head")
_SkinClass = FindClass("CustomizationType_Skin")

def _FormatSkills(skills):
	result = list(skill.Grade for skill in skills)
	if len(result) < 1:
		return None

	if Output['class'] == "Mechromancer":
		del result[24]
	elif Output['class'] == "Psycho":
		del result[37:39]
		del result[13]
	del result[0]

	return result


def _FormatInventoryName(prefixPart, suffixPart, definitionData = None):
	prefix = prefixPart.PartName if (
		prefixPart is not None and prefixPart.PartName is not None and prefixPart.PartName != ""
		) else None

	suffix = suffixPart.PartName if (
		suffixPart is not None and suffixPart.PartName is not None and suffixPart.PartName != ""
		) else None

	if suffix is not None:
		return f"{prefix} {suffix}" if prefix is not None else suffix
	elif prefix is not None:
		return prefix
	elif definitionData is not None:
		return definitionData.ItemDefinition.ItemName
	return None

_ItemClassOutputs = {
	"ShieldDefinition": 'shield',
	"WillowShield": 'shield',
	"GrenadeModDefinition": 'grenade',
	"WillowGrenadeMod": 'grenade',
	"ClassModDefinition": 'classMod',
	"CrossDLCClassModDefinition": 'classMod',
	"WillowClassMod": 'classMod',
	"ArtifactDefinition": 'relic',
	"WillowArtifact": 'relic',
}

def _FinishSaveGameLoad(caller: UObject, function: UFunction, params: FStruct):
	saveGame = None

	if params is None:
		saveGame = caller.LastLoadedSaveGame
	else:
		caller.FinishSaveGameLoad(params.SaveGame, params.LoadResult, params.bUpdatePRI, params.bLoadedNewSaveGame, params.bLoadPlayer, params.bShouldRefreshStandIn, params.LoadPlayerBehavior)
		saveGame = params.SaveGame

	global Output
	Output = {
		'name': None,
		'class': None,
		'head': None,
		'skin': None,
		'level': None,
		'OPLevel': None,
		'playthrough': None,
		'currentPlaythrough': None,
		'currentOPLevel': None,
		'map': None,
		'weapons': [None, None, None, None],
		'shield': None,
		'grenade': None,
		'classMod': None,
		'relic': None,
		'skills': None,
	}

	standIn = caller.GetPrimaryPlayerStandIn()
	if standIn is not None:
		headCustomization = standIn.GetDesiredCustomizationOfType(_HeadClass)
		if headCustomization is not None:
			Output['head'] = headCustomization.CustomizationName

		skinCustomization = standIn.GetDesiredCustomizationOfType(_SkinClass)
		if skinCustomization is not None:
			Output['skin'] = skinCustomization.CustomizationName

	Output['name'] = saveGame.UIPreferences.CharacterName
	Output['class'] = saveGame.PlayerClassDefinition.CharacterNameId.CharacterClassId.ClassName
	Output['level'] = saveGame.ExpLevel
	Output['OPLevel'] = saveGame.NumOverpowerLevelsUnlocked
	Output['playthrough'] = saveGame.PlaythroughsCompleted
	Output['currentPlaythrough'] = saveGame.LastPlaythroughNumber
	Output['currentOPLevel'] = saveGame.LastOverpowerChoice

	teleporter = saveGame.LastVisitedTeleporter
	if teleporter is None:
		teleporter = saveGame.MissionPlaythroughs[saveGame.LastPlaythroughNumber].LastVisitedTeleporter
	if teleporter is not None:
		Output['map'] = caller.GetWillowGlobals().GetFastTravelStationsLookup().GetLevelName(teleporter)

	for weapon in saveGame.WeaponData:
		weaponIndex = weapon.QuickSlot - 1
		if weaponIndex >= 0:
			prefixPart = weapon.WeaponDefinitionData.PrefixPartDefinition
			suffixPart = weapon.WeaponDefinitionData.TitlePartDefinition
			Output['weapons'][weaponIndex] = _FormatInventoryName(prefixPart, suffixPart)

	for item in saveGame.ItemData:
		if not item.bEquipped:
			continue

		definitionData = item.DefinitionData
		className = definitionData.ItemDefinition.Class.Name
		nameOutput = _ItemClassOutputs.get(definitionData.ItemDefinition.Class.Name)
		if nameOutput is None:
			continue

		prefixPart = definitionData.PrefixItemNamePartDefinition
		suffixPart = definitionData.TitleItemNamePartDefinition
		Output[nameOutput] = _FormatInventoryName(prefixPart, suffixPart, definitionData)

	Output['skills'] = _FormatSkills(saveGame.SkillData)

	_SaveOutput()
	return False

def _ClientSetSkillGrade(caller: UObject, function: UFunction, params: FStruct):
	Output['skills'] = _FormatSkills(caller.PlayerSkillTree.Skills)
	_SaveOutput()
	return True

def _ClientOnExpLevelChange(caller: UObject, function: UFunction, params: FStruct):
	Output['level'] = caller.PlayerReplicationInfo.ExpLevel
	_SaveOutput()
	return True

def _ClientIncrementOverpowerLevel(caller: UObject, function: UFunction, params: FStruct):
	newOPlevel = caller.PlayerReplicationInfo.NumOverpowerLevelsUnlocked + params.IncrementAmount
	if newOPlevel <= params.MaximumValue:
		Output['OPLevel'] = newOPlevel
		_SaveOutput()
	return True

def _OnPlaythroughCompleted(caller: UObject, function: UFunction, params: FStruct):
	if params.PlayThroughNumber < 2:
		Output['playthrough'] = params.PlayThroughNumber + 1
		_SaveOutput()
	return True

def _OnClose(caller: UObject, function: UFunction, params: FStruct):
	playerController = caller.WPCOwner
	Output['name'] = playerController.PlayerPreferredCharacterName
	Output['skills'] = _FormatSkills(playerController.PlayerSkillTree.Skills)

	playerPawn = playerController.Pawn
	Output['head'] = playerPawn.HeadCustomizationData.MyDefinition.CustomizationName
	Output['skin'] = playerPawn.SkinCustomizationData.MyDefinition.CustomizationName

	Output['map'] = GetEngine().GetCurrentWorldInfo().GetMapName(True)

	_SaveOutput()
	return True


_ReadyPrecededUnready = False

def _InventoryReadied(caller: UObject, function: UFunction, params: FStruct):
	if caller is not GetEngine().GamePlayers[0].Actor.GetPawnInventoryManager():
		return True

	item = params.Inv
	itemClass = item.Class.Name

	caller.InventoryReadied(item)

	global _ReadyPrecededUnready
	_ReadyPrecededUnready = True
	_RegisterHook(_Tick, "WillowGame.WillowGameViewportClient")

	if itemClass == "WillowWeapon":
		weaponIndex = item.QuickSelectSlot - 1
		Output['weapons'][weaponIndex] = item.GetShortHumanReadableName()
	else:
		itemOutput = _ItemClassOutputs.get(itemClass)
		if itemOutput is not None:
			Output[itemOutput] = item.GetShortHumanReadableName()

	_SaveOutput()
	return False

def _RemoveFromInventory(caller: UObject, function: UFunction, params: FStruct):
	if caller is not GetEngine().GamePlayers[0].Actor.GetPawnInventoryManager():
		return True

	item = params.ItemToRemove
	itemClass = item.Class.Name

	global _ReadyPrecededUnready
	if _ReadyPrecededUnready:
		_ReadyPrecededUnready = False
		_RemoveHook(_Tick, "WillowGame.WillowGameViewportClient")
		return True

	if itemClass == "WillowWeapon":
		if item.QuickSelectSlot != 0:
			weaponIndex = item.QuickSelectSlot - 1
			Output['weapons'][weaponIndex] = None
	else:
		itemOutput = _ItemClassOutputs.get(itemClass)
		if itemOutput is not None:
			Output[itemOutput] = None

	_SaveOutput()
	return True

def _Tick(caller: UObject, function: UFunction, params: FStruct):
	global _ReadyPrecededUnready
	_ReadyPrecededUnready = False
	_RemoveHook(_Tick, "WillowGame.WillowGameViewportClient")
	return True

def _SwitchQuickSlot(caller: UObject, function: UFunction, params: FStruct):
	if caller is not GetEngine().GamePlayers[0].Actor.GetPawnInventoryManager():
		return True

	oldWeaponIndex = params.Thing.QuickSelectSlot - 1
	newWeaponIndex = params.NewWeaponSlot - 1
	oldWeapon = Output['weapons'][oldWeaponIndex]
	newWeapon = Output['weapons'][newWeaponIndex]
	Output['weapons'][oldWeaponIndex] = newWeapon
	Output['weapons'][newWeaponIndex] = oldWeapon
	_SaveOutput()
	return True

def _NotifyTeleported(caller: UObject, function: UFunction, params: FStruct):
	playerController = caller.Controller
	Output['name'] = playerController.PlayerPreferredCharacterName

	playerClass = playerController.PlayerClass
	if playerClass is not None:
		Output['class'] = playerController.PlayerClass.CharacterNameId.CharacterClassId.ClassName

	if caller.HeadCustomizationData is not None:
		Output['head'] = caller.HeadCustomizationData.MyDefinition.CustomizationName
	if caller.SkinCustomizationData is not None:
		Output['skin'] = caller.SkinCustomizationData.MyDefinition.CustomizationName

	playerReplicationInfo = caller.PlayerReplicationInfo
	Output['level'] = playerReplicationInfo.ExpLevel
	Output['OPLevel'] = playerReplicationInfo.NumOverpowerLevelsUnlocked
	Output['playthrough'] = playerReplicationInfo.HighestCompletedPlaythrough

	gameReplicationInfo = GetEngine().GetCurrentWorldInfo().GRI
	Output['currentPlaythrough'] = gameReplicationInfo.CurrentPlaythrough
	Output['currentOPLevel'] = gameReplicationInfo.OverpowerLevelModifier

	Output['map'] = GetEngine().GetCurrentWorldInfo().GetMapName(True)

	Output['skills'] = _FormatSkills(playerController.PlayerSkillTree.Skills)

	_SaveOutput()
	return True


def _RegisterHook(hook, prefix="WillowGame.WillowPlayerController"):
	name = prefix + '.' + hook.__name__[1:]
	RegisterHook(name, "LiveFeed." + name, hook)

def _RemoveHook(hook, prefix="WillowGame.WillowPlayerController"):
	name = prefix + '.' + hook.__name__[1:]
	RemoveHook(name, "LiveFeed." + name)


class LiveFeed(ModMenu.SDKMod):
	Name: str = "Live Feed"
	Version: str = "2.0.1"
	Description: str = f"Live updates character information to &lt;{OutputPath}&gt;."
	Author: str = "mopioid"
	Types: ModTypes = ModTypes.Utility

	SaveEnabledState: ModMenu.EnabledSaveType = ModMenu.EnabledSaveType.LoadOnMainMenu

	def __init__(self):
		ModMenu.LoadModSettings(self)

	def Enable(self):
		_FinishSaveGameLoad(GetEngine().GamePlayers[0].Actor, None, None)

		_RegisterHook(_FinishSaveGameLoad)
		_RegisterHook(_ClientSetSkillGrade)
		_RegisterHook(_ClientIncrementOverpowerLevel)
		_RegisterHook(_ClientOnExpLevelChange)
		_RegisterHook(_OnPlaythroughCompleted)
		_RegisterHook(_NotifyTeleported, "WillowGame.WillowPlayerPawn")
		_RegisterHook(_OnClose, "WillowGame.CustomizationGFxMovie")
		_RegisterHook(_OnClose, "WillowGame.CharacterSelectionReduxGFxMovie")
		_RegisterHook(_InventoryReadied, "WillowGame.WillowInventoryManager")
		_RegisterHook(_RemoveFromInventory, "WillowGame.WillowInventoryManager")
		_RegisterHook(_SwitchQuickSlot, "WillowGame.WillowInventoryManager")

	def Disable(self):
		_RemoveHook(_FinishSaveGameLoad)
		_RemoveHook(_ClientSetSkillGrade)
		_RemoveHook(_ClientIncrementOverpowerLevel)
		_RemoveHook(_ClientOnExpLevelChange)
		_RemoveHook(_OnPlaythroughCompleted)
		_RemoveHook(_NotifyTeleported, "WillowGame.WillowPlayerPawn")
		_RemoveHook(_OnClose, "WillowGame.CustomizationGFxMovie")
		_RemoveHook(_OnClose, "WillowGame.CharacterSelectionReduxGFxMovie")
		_RemoveHook(_InventoryReadied, "WillowGame.WillowInventoryManager")
		_RemoveHook(_RemoveFromInventory, "WillowGame.WillowInventoryManager")
		_RemoveHook(_SwitchQuickSlot, "WillowGame.WillowInventoryManager")

ModMenu.RegisterMod(LiveFeed())
