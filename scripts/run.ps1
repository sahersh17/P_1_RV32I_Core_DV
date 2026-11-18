param(
    [string]$CadRoot = (Join-Path $env:USERPROFILE 'Downloads/oss-cad-suite'),
    [ValidateRange(0, 100000)][int]$RandomPrograms = 100,
    [switch]$SingleCycle,
    [switch]$Waves
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$compiler = (Get-Command g++ -ErrorAction Stop).Source
$cad = (Resolve-Path -LiteralPath $CadRoot).Path
$previousPath = $env:PATH
$previousVerilatorRoot = $env:VERILATOR_ROOT

Push-Location -LiteralPath $root
try {
    $env:PATH = "$cad\bin;$cad\lib;$previousPath"
    $env:VERILATOR_ROOT = Join-Path $cad 'share/verilator'
    $include = Join-Path $env:VERILATOR_ROOT 'include'
    $variant = if ($SingleCycle) { 'single-cycle' } else { 'pipeline' }
    $build = "build/verilator-$variant"
    $simulator = "$build/Vtb_core.exe"
    $rtl = (Get-ChildItem -LiteralPath rtl -Filter '*.sv').FullName
    $verilatorArgs = @('--cc', '--main', '--timing', '--trace', '--top-module', 'tb_core', '--Mdir', $build)
    if ($SingleCycle) { $verilatorArgs += '-DSINGLE_CYCLE' }
    $verilatorArgs += $rtl
    $verilatorArgs += 'tb/tb_core.sv'

    New-Item -ItemType Directory -Path $build -Force | Out-Null
    & "$cad\bin\verilator_bin.exe" @verilatorArgs
    if ($LASTEXITCODE) { throw "Verilator failed with exit code $LASTEXITCODE" }

    $generated = (Get-ChildItem -LiteralPath $build -Filter '*.cpp').FullName
    $runtime = @('verilated.cpp', 'verilated_timing.cpp', 'verilated_threads.cpp', 'verilated_vcd_c.cpp') |
        ForEach-Object { Join-Path $include $_ }
    & $compiler -std=c++20 -O1 -DVL_TIME_CONTEXT -DVM_TRACE=1 -DVM_TRACE_VCD=1 -I $build -I $include -I "$include/vltstd" -o $simulator @generated @runtime -pthread
    if ($LASTEXITCODE) { throw "C++ build failed with exit code $LASTEXITCODE" }

    $options = @('--prebuilt', $simulator, '--random', $RandomPrograms)
    if ($SingleCycle) { $options += '--single-cycle' }
    if ($Waves) { $options += '--waves' }
    python tb/run.py @options
    if ($LASTEXITCODE) { throw "Regression failed with exit code $LASTEXITCODE" }
} finally {
    $env:PATH = $previousPath
    $env:VERILATOR_ROOT = $previousVerilatorRoot
    Pop-Location
}
