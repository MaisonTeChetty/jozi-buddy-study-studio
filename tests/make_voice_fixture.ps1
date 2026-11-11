param([switch]$SpelledAcronym)
Add-Type -AssemblyName System.Speech
$fixtureRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\tmp'))
[System.IO.Directory]::CreateDirectory($fixtureRoot) | Out-Null
$speechFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$phrases = @{
    'voice-question.wav' = 'Hi Jozi. What does least privilege mean?'
    'voice-interruption.wav' = 'Please explain multi factor authentication instead.'
}
if ($SpelledAcronym) {
    $phrases['voice-question.wav'] = 'Hi Jozi. What does A E S dash G C M do?'
}
foreach ($item in $phrases.GetEnumerator()) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $synth.SetOutputToWaveFile((Join-Path $fixtureRoot $item.Key), $speechFormat)
        $synth.Speak($item.Value)
    } finally {
        $synth.Dispose()
    }
}
Write-Output 'Synthetic voice fixtures created; no microphone audio was recorded.'
