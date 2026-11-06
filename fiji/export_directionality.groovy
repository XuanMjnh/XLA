#@ File(label="Grayscale input image") inputFile
#@ File(label="Output directory", style="directory") outputDir
#@ Integer(label="Number of bins", value=180, min=18, max=720) bins
#@ Boolean(label="Apply Gaussian sigma=1 before analysis", value=true) gaussian

// Run in the Fiji Script Editor with Language=Groovy, not in CPython.
// Plugin API exercised by DirectionalityBatch.java using the official 2.3.0 JAR.
import ij.IJ
import ij.ImagePlus
import ij.plugin.filter.GaussianBlur
import fiji.analyze.directionality.Directionality_
import java.util.Locale

ImagePlus source = IJ.openImage(inputFile.getAbsolutePath())
if (source == null) throw new IllegalArgumentException("Cannot read the input image.")
if (source.getStackSize() != 1 || source.getBitDepth() == 24)
    throw new IllegalArgumentException("Use one grayscale image, not RGB or an image stack.")
if (source.getWidth() < 32 || source.getHeight() < 32)
    throw new IllegalArgumentException("Image must be at least 32x32 pixels.")
outputDir.mkdirs()
def processor = source.getProcessor().convertToFloatProcessor()
if (gaussian) new GaussianBlur().blurGaussian(processor, 1.0)
ImagePlus working = new ImagePlus(source.getTitle(), processor)
def methods = [
    "local_gradient": Directionality_.AnalysisMethod.LOCAL_GRADIENT_ORIENTATION,
    "fourier_components": Directionality_.AnalysisMethod.FOURIER_COMPONENTS
]
methods.each { label, method ->
    def analyzer = new Directionality_()
    analyzer.setImagePlus(working)
    analyzer.setMethod(method)
    analyzer.setBinNumber(bins)
    analyzer.setBinRange(0.0,180.0)
    analyzer.setBuildOrientationMapFlag(false)
    analyzer.computeHistograms()
    double[] angles = analyzer.getBins() // API returns DEGREES.
    double[] histogram = analyzer.getHistograms().get(0)
    File target = new File(outputDir, label+".csv")
    target.withWriter("UTF-8") { writer ->
        writer.write("angle_deg,weight\n")
        for (int i=0; i<angles.length; i++) {
            writer.write(String.format(Locale.US,"%.12g,%.12g%n",angles[i],histogram[i]))
        }
    }
    double total = histogram.sum()
    if (Double.isFinite(total) && total > 0) {
        analyzer.fitHistograms()
        double[] fit = analyzer.getFitAnalysis().get(0)
        new File(outputDir, label+"_fit.csv").withWriter("UTF-8") { writer ->
            writer.write("center_deg,std_deg,amount,goodness_of_fit\n")
            writer.write(String.format(Locale.US,"%.12g,%.12g,%.12g,%.12g%n",Math.toDegrees(fit[0]),Math.toDegrees(fit[1]),fit[2],fit[3]))
        }
    }
    IJ.log("Saved: "+target.getAbsolutePath())
}
new File(outputDir,"settings.txt").text = "Input="+inputFile.getAbsolutePath()+"\nBins="+bins+
    "\nRange=0..180 degrees, structure angles\nGaussianSigma="+(gaussian?1:0)+
    "\nImageJ="+IJ.getVersion()+"\nPlugin="+Directionality_.class.getProtectionDomain().getCodeSource().getLocation()+"\n"
source.close()
IJ.log("Finished. Compare RAW histograms and retain the settings file.")
