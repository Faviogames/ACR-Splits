# Rasterize the existing two-slash vector mark into a multi-resolution Windows icon.
Add-Type -AssemblyName System.Drawing
$taskFrames=@()
foreach($taskSize in @(16,24,32,48,64,128,256)){
  $taskBitmap=[Drawing.Bitmap]::new($taskSize,$taskSize)
  $taskGraphics=[Drawing.Graphics]::FromImage($taskBitmap)
  $taskStream=[IO.MemoryStream]::new()
  try{
    $taskGraphics.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $taskGraphics.Clear([Drawing.Color]::FromArgb(26,26,28))
    $taskGraphics.ScaleTransform($taskSize/64.0,$taskSize/64.0)
    $taskBrush=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(255,48,59))
    try{
      $taskGraphics.FillPolygon($taskBrush,[Drawing.PointF[]]@([Drawing.PointF]::new(7,48),[Drawing.PointF]::new(28,16),[Drawing.PointF]::new(40,16),[Drawing.PointF]::new(19,48)))
      $taskGraphics.FillPolygon($taskBrush,[Drawing.PointF[]]@([Drawing.PointF]::new(27,48),[Drawing.PointF]::new(48,16),[Drawing.PointF]::new(60,16),[Drawing.PointF]::new(39,48)))
    }finally{$taskBrush.Dispose()}
    $taskBitmap.Save($taskStream,[Drawing.Imaging.ImageFormat]::Png)
    $taskFrames+=@{Size=$taskSize;Bytes=$taskStream.ToArray()}
  }finally{$taskStream.Dispose();$taskGraphics.Dispose();$taskBitmap.Dispose()}
}
$taskOutput=[IO.File]::Create((Join-Path $PSScriptRoot 'ui/assets/app.ico'))
$taskWriter=[IO.BinaryWriter]::new($taskOutput)
try{
  $taskWriter.Write([uint16]0);$taskWriter.Write([uint16]1);$taskWriter.Write([uint16]$taskFrames.Count)
  $taskOffset=6+16*$taskFrames.Count
  foreach($taskFrame in $taskFrames){
    $taskDimension=if($taskFrame.Size -eq 256){0}else{$taskFrame.Size}
    $taskWriter.Write([byte]$taskDimension);$taskWriter.Write([byte]$taskDimension)
    $taskWriter.Write([byte]0);$taskWriter.Write([byte]0);$taskWriter.Write([uint16]1);$taskWriter.Write([uint16]32)
    $taskWriter.Write([uint32]$taskFrame.Bytes.Length);$taskWriter.Write([uint32]$taskOffset)
    $taskOffset+=$taskFrame.Bytes.Length
  }
  foreach($taskFrame in $taskFrames){$taskWriter.Write([byte[]]$taskFrame.Bytes)}
}finally{$taskWriter.Dispose();$taskOutput.Dispose()}
