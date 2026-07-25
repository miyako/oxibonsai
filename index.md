---
layout: default
---

![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm%20|%20win-64&color=blue)
[![license](https://img.shields.io/github/license/miyako/oxibonsai)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/oxibonsai/total)

# Use oxibonsai from 4D

#### Abstract

[**oxibonsai**](https://github.com/cool-japan/oxibonsai) is a zero-FFI, zero-C/C++ inference engine for **PrismML**'s Bonsai family. It runs on CPU (SIMD), Apple Silicon (Metal), and NVIDIA (CUDA) without depending on llama.cpp, BLAS, or any C/Fortran runtime.

```4d
var $oxibonsai : cs.oxibonsai

var $homeFolder : 4D.Folder
$homeFolder:=Folder(fk home folder).folder(".GGUF")

var $file : 4D.File
var $URL : Text
var $port : Integer
var $huggingface : cs.event.huggingface

var $event : cs.event.event
$event:=cs.event.event.new()
$event.onError:=Formula(ALERT($2.message))
$event.onSuccess:=Formula(ALERT($2.models.extract("name").join(",")+" loaded!"))
$event.onData:=Formula(LOG EVENT(Into 4D debug message; This.file.fullName+":"+String((This.range.end/This.range.length)*100; "###.00%")))
$event.onData:=Formula(MESSAGE(This.file.fullName+":"+String((This.range.end/This.range.length)*100; "###.00%")))
$event.onResponse:=Formula(LOG EVENT(Into 4D debug message; This.file.fullName+":download complete"))
$event.onResponse:=Formula(MESSAGE(This.file.fullName+":download complete"))
$event.onTerminate:=Formula(LOG EVENT(Into 4D debug message; (["process"; $1.pid; "terminated!"].join(" "))))

var $folder : 4D.Folder
var $path : Text

$port:=8080

If (True)
    
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
    
    var $huggingfaces : cs.event.huggingfaces
    
    $huggingface:=cs.event.huggingface.new($folder; $URL; [$path])
    $huggingfaces:=cs.event.huggingfaces.new([$huggingface])
    
    $oxibonsai:=cs.oxibonsai.new($port; $huggingfaces; $homeFolder; $options; $event)
    
End if 
```

#### AI Kit compatibility

The API is compatible with the following [Open AI](https://platform.openai.com/docs/api-reference/) endpoints: 

|Class|API|Availability|
|-|-|:-:|
|Models|`/v1/models`|✅|
|Chat|`/v1/chat/completions`|✅|
|Images|`/v1/images/generations`||
|Moderations|`/v1/moderations`||
|Embeddings|`/v1/embeddings`||
|Files|`/v1/files`||
