//%attributes = {"invisible":true}
var $parameter : Text
var $unused : Integer
$unused:=Get database parameter:C643(User param value:K37:94; $parameter)
var $paths : Collection
$paths:=Split string:C1554($parameter; ",")
var $project; $report : 4D:C1709.File
$project:=File:C1566($paths[0]; fk posix path:K87:1)
$report:=File:C1566($paths[1]; fk posix path:K87:1)
var $options; $status : Object
$options:={generateSymbols: False:C215; generateSyntaxFile: True:C214}
$options.components:=New collection:C1472
var $name : Text
var $component : 4D:C1709.File
For each ($name; ["tcp"; "workers"; "event"])
	$component:=$project.parent.parent.folder("Components").folder($name+".4dbase").file($name+".4DZ")
	$options.components.push($component)
End for each
$options.targets:=["arm64_macOS_lib"; "x86_64_generic"]
$status:=Compile project:C1760($project; $options)
$report.setText(JSON Stringify:C1217($status))
QUIT 4D:C291
