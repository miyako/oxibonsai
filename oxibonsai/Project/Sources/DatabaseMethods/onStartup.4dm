var $oxibonsai : cs:C1710.oxibonsai

var $homeFolder : 4D:C1709.Folder
$homeFolder:=Folder:C1567(fk home folder:K87:24).folder(".GGUF")

var $file : 4D:C1709.File
var $URL : Text
var $port : Integer
var $huggingface : cs:C1710.event.huggingface

var $event : cs:C1710.event.event
$event:=cs:C1710.event.event.new()
$event.onError:=Formula:C1597(ALERT:C41($2.message))
$event.onSuccess:=Formula:C1597(ALERT:C41($2.models.extract("name").join(",")+" loaded!"))
$event.onData:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; This:C1470.file.fullName+":"+String:C10((This:C1470.range.end/This:C1470.range.length)*100; "###.00%")))
$event.onData:=Formula:C1597(MESSAGE:C88(This:C1470.file.fullName+":"+String:C10((This:C1470.range.end/This:C1470.range.length)*100; "###.00%")))
$event.onResponse:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; This:C1470.file.fullName+":download complete"))
$event.onResponse:=Formula:C1597(MESSAGE:C88(This:C1470.file.fullName+":download complete"))
$event.onTerminate:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; (["process"; $1.pid; "terminated!"].join(" "))))

var $folder : 4D:C1709.Folder
var $path : Text

$port:=8080

If (True:C214)
	
	$folder:=$homeFolder.folder("Bonsai")
	$path:="Bonsai-8B.gguf"
	$URL:="prism-ml/Bonsai-8B-gguf"
	
	var $options : Object
	
	$max_seq_len:=1024
	$pool_size:=4
	$max_concurrent_requests:=4
	$request_timeout_ms:=60000
	
	$options:={\
		request_timeout_ms: $request_timeout_ms; \
		max_concurrent_requests: $max_concurrent_requests; \
		pool_size: $pool_size; \
		max_seq_len: $max_seq_len\
		}
	
	var $huggingfaces : cs:C1710.event.huggingfaces
	
	$huggingface:=cs:C1710.event.huggingface.new($folder; $URL; [$path])
	$huggingfaces:=cs:C1710.event.huggingfaces.new([$huggingface])
	
	$oxibonsai:=cs:C1710.oxibonsai.new($port; $huggingfaces; $homeFolder; $options; $event)
	
End if 