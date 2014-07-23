# -*- coding: utf-8 -*-
from __future__ import division, unicode_literals
import re
from collections import defaultdict
from datetime import date, datetime
from . import config
from . import markdown
from .messages import *
from .htmlhelpers import *

class MetadataManager:
    @property
    def hasMetadata(self):
        return len(self.manuallySetKeys) > 0

    @property
    def vshortname(self):
        if self.level is not None:
            return "{0}-{1}".format(self.shortname, self.level)
        return self.shortname

    def __init__(self):
        # required metadata
        self.status = None
        self.ED = None
        self.abstract = []
        self.shortname = None
        self.level = None

        # optional metadata
        self.TR = None
        self.title = None
        self.h1 = None
        self.statusText = ""
        self.date = datetime.utcnow().date()
        self.deadline = None
        self.group = None
        self.editors = []
        self.previousEditors = []
        self.previousVersions = []
        self.warning = None
        self.atRisk = []
        self.ignoredTerms = []
        self.testSuite = None
        self.mailingList = None
        self.mailingListArchives = None
        self.boilerplate = {'omitSections':set()}
        self.versionHistory = None
        self.logo = ""

        self.otherMetadata = defaultdict(list)

        self.singleValueKeys = {
            "Title": "title",
            "H1": "h1",
            "Status": "status",
            "Status Text": "statusText",
            "ED": "ED",
            "URL": "ED", # URL is a synonym for ED
            "Shortname": "shortname",
            "Level": "level",
            "TR": "TR",
            "Warning": "warning",
            "Group": "group",
            "Date": "date",
            "Deadline": "deadline",
            "Test Suite": "testSuite",
            "Mailing List": "mailingList",
            "Mailing List Archives": "mailingListArchives",
            "Boilerplate": "boilerplate",
            "Version History": "versionHistory",
            "Logo": "logo"
        }

        self.multiValueKeys = {
            "Editor": "editors",
            "Former Editor": "previousEditors",
            "Abstract": "abstract",
            "Previous Version": "previousVersions",
            "At Risk": "atRisk",
            "Ignored Terms": "ignoredTerms",
            "Link Defaults": ""
        }

        self.knownKeys = self.singleValueKeys.viewkeys() | self.multiValueKeys.viewkeys()

        self.manuallySetKeys = set()

        # Input transformers
        self.customInput = {
            "Status": setStatus,
            "Group": convertGroup,
            "Date": parseDate,
            "Deadline": parseDate,
            "Level": parseLevel,
            "Warning": convertWarning,
            "Editor": parseEditor,
            "Former Editor": parseEditor,
            "Ignored Terms": parseIgnoredTerms,
            "Link Defaults": parseLinkDefaults,
            "Boilerplate": parseBoilerplate
        }

        # Alternate output handlers
        self.customOutput = {
            "Link Defaults": saveLinkDefaults
        }

    def addData(self, key, val, default=False):
        key = key.strip()
        val = val.strip()

        if key.startswith("!"):
            key = key[1:]
            self.otherMetadata[key].append(val)
            return

        if key not in ("ED", "TR", "URL"):
            key = key.title()

        if not (key in self.knownKeys or key.startswith("!")):
            die('Unknown metadata key "{0}". Prefix custom keys with "!".', key)
            return

        if key in self.knownKeys and not default:
            self.manuallySetKeys.add(key)

        if default and key in self.manuallySetKeys:
            return

        if key in self.customInput:
            val = self.customInput[key](key, val)

        if key in self.customOutput:
            self.customOutput[key](key, val)
            return

        if key in self.singleValueKeys:
            setattr(self, self.singleValueKeys[key], val)
        else:
            if isinstance(val, list):
                getattr(self, self.multiValueKeys[key]).extend(val)
            else:
                getattr(self, self.multiValueKeys[key]).append(val)

    def addDefault(self, key, val):
        self.addData(key, val, default=True)

    def finish(self):
        self.validate()

    def validate(self):
        if not self.hasMetadata:
            die("The document requires at least one metadata block.")
            return

        requiredSingularKeys = [
            ('status', 'Status'),
            ('ED', 'ED'),
            ('shortname', 'Shortname')
        ]
        requiredMultiKeys = [
            ('abstract', 'Abstract'),
            ('editors', 'Editor')
        ]
        errors = []
        for attr, name in requiredSingularKeys:
            if getattr(self, attr) is None:
                errors.append("    Missing a '{0}' entry.".format(name))
        for attr, name in requiredMultiKeys:
            if len(getattr(self, attr)) == 0:
                errors.append("    Must provide at least one '{0}' entry.".format(name))
        # Level is optional for some statuses.
        if self.level is None and self.status not in config.unlevelledStatuses:
            errors.append("    Missing a 'Level' entry.")
        if errors:
            die("Not all required metadata was provided:\n{0}", "\n".join(errors))
            return

    def fillTextMacros(self, macros, doc=None):
        # Fills up a set of text macros based on metadata.
        if self.title:
            macros["title"] = self.title
            macros["spectitle"] = self.title
        if self.h1:
            macros["spectitle"] = self.h1
        macros["shortname"] = self.shortname
        if self.status:
            macros["statusText"] = self.statusText
        macros["vshortname"] = self.vshortname
        if self.status in config.shortToLongStatus:
            macros["longstatus"] = config.shortToLongStatus[self.status]
        else:
            die("Unknown status '{0}' used.", self.status)
        if self.status in ("LCWD", "FPWD"):
            macros["status"] = "WD"
        else:
            macros["status"] = self.status
        if self.TR:
            macros["latest"] = self.TR
        if self.abstract:
            macros["abstract"] = "\n".join(markdown.parse(self.abstract))
            macros["abstractattr"] = escapeAttr("  ".join(self.abstract).replace("<<","<").replace(">>",">"))
        macros["year"] = unicode(self.date.year)
        macros["date"] = unicode(self.date.strftime("{0} %B %Y".format(self.date.day)), encoding="utf-8")
        macros["cdate"] = unicode(self.date.strftime("%Y%m%d"), encoding="utf-8")
        macros["isodate"] = unicode(self.date.strftime("%Y-%m-%d"), encoding="utf-8")
        if self.deadline:
            macros["deadline"] = unicode(self.deadline.strftime("{0} %B %Y".format(self.deadline.day)), encoding="utf-8")
        if self.status in config.TRStatuses:
            macros["version"] = "http://www.w3.org/TR/{year}/{status}-{vshortname}-{cdate}/".format(**macros)
        else:
            macros["version"] = self.ED
        macros["annotations"] = config.testAnnotationURL
        if doc and self.vshortname in doc.testSuites:
            macros["testsuite"] = doc.testSuites[self.vshortname]['vshortname']
        macros["logo"] = self.logo


def setStatus(key, val):
    config.doc.refs.status = val
    return val

def convertGroup(key, val):
    return val.lower()

def parseDate(key, val):
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except:
        die("The {0} field must be in the format YYYY-MM-DD - got \"{1}\" instead.", key, val)

def parseLevel(key, val):
    return config.HierarchicalNumber(val)

def convertWarning(key, val):
    if val.lower() == "obsolete":
        return "warning-obsolete"
    if val.lower() == "not ready":
        return "warning-not-ready"
    match = re.match("Replaced By +(.+)", val, re.I)
    if match:
        config.textMacros['replacedby'] = match.group(1)
        return "warning-replaced-by"
    match = re.match("New Version +(.+)", val, re.I)
    if match:
        config.textMacros['replacedby'] = match.group(1)
        return "warning-new-version"
    die('Unknown value for "{0}" metadata.', key)

def parseEditor(key, val):
    match = re.match("([^,]+) ,\s* ([^,]*) ,?\s* ([^,]*) ,?\s* ([^,]*)", val, re.X)
    pieces = [piece.strip() for piece in val.split(',')]
    def looksLinkish(string):
        return re.match(ur"\w+:", string) or looksEmailish(string)
    def looksEmailish(string):
        return re.match(ur".+@.+\..+", string)
    data = {
        'name' : pieces[0],
        'org'  : None,
        'link' : None,
        'email': None
    }
    if len(pieces) == 4 and looksLinkish(pieces[2]) and looksLinkish(pieces[3]):
        data['org'] = pieces[1]
        if looksEmailish(pieces[2]):
            data['email'] = pieces[2]
            data['link'] = pieces[3]
        else:
            data['link'] = pieces[2]
            data['email'] = pieces[3]
    elif len(pieces) == 3 and looksLinkish(pieces[1]) and looksLinkish(pieces[2]):
        if looksEmailish(pieces[1]):
            data['email'] = pieces[1]
            data['link'] = pieces[2]
        else:
            data['link'] = pieces[1]
            data['email'] = pieces[2]
    elif len(pieces) == 3 and looksLinkish(pieces[2]):
        data['org'] = pieces[1]
        if looksEmailish(pieces[2]):
            data['email'] = pieces[2]
        else:
            data['link'] = pieces[2]
    elif len(pieces) == 2:
        # See if the piece looks like a link/email
        if looksLinkish(pieces[1]):
            if looksEmailish(pieces[1]):
                data['email'] = pieces[1]
            else:
                data['link'] = pieces[1]
        else:
            data['org'] = pieces[1]
    elif len(pieces) == 1:
        pass
    else:
        die("'{0}' format is '<name>, <company>?, <email-or-contact-page>?. Got:\n{1}", key, val)
    return data


def parseIgnoredTerms(key, val):
    return [term.strip().lower() for term in val.split(',')]

def parseLinkDefaults(key, val):
    defaultSpecs = defaultdict(list)
    for default in val.split(","):
        match = re.match("^([\w\d-]+)  (?:\s+\( ({0}) (?:\s+(TR|ED))? \) )  \s+(.*)$".format("|".join(config.dfnTypes.union(["dfn"]))), default.strip(), re.X)
        if match:
            spec = match.group(1)
            type = match.group(2)
            status = match.group(3)
            terms = match.group(4).split('/')
            dfnFor = None
            for term in terms:
                defaultSpecs[term.strip()].append((spec, type, status, dfnFor))
        else:
            die("'{0}' is a comma-separated list of '<spec> (<dfn-type>) <terms>'. Got:\n{1}", key, default)
            continue
    return defaultSpecs

def saveLinkDefaults(key, val):
    for term, defaults in val.items():
        for default in defaults:
            config.doc.refs.defaultSpecs[term].append(default)

def parseBoilerplate(key, val):
    boilerplate = {'omitSections':set()}
    for command in val.split(","):
        command = command.strip()
        if re.match("omit [\w-]+$", command):
            boilerplate['omitSections'].add(command[5:])
    return boilerplate



def parse(lines):
    # Given HTML document text, in the form of an array of text lines,
    # extracts all <pre class=metadata> lines and parses their contents.
    # Returns a MetadataManager object and the text lines (with the
    # metadata-related lines removed).

    newlines = []
    inMetadata = False
    lastKey = None
    md = MetadataManager()
    for line in lines:
        if not inMetadata and re.match(r"<pre .*class=.*metadata.*>", line):
            inMetadata = True
            continue
        elif inMetadata and re.match(r"</pre>\s*", line):
            inMetadata = False
            continue
        elif inMetadata:
            if lastKey and (line.strip() == "") or re.match(r"\s+", line):
                md.addData(lastKey, line.lstrip())
            elif re.match(r"([^:]+):\s*(.*)", line):
                match = re.match(r"([^:]+):\s*(.*)", line)
                md.addData(match.group(1), match.group(2))
                lastKey = match.group(1)
            else:
                die("Incorrectly formatted metadata line:\n{0}", line)
                continue
        else:
            newlines.append(line)
    return md, newlines
