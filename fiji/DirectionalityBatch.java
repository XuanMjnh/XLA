import fiji.analyze.directionality.Directionality_;

import ij.IJ;
import ij.ImagePlus;
import ij.plugin.filter.GaussianBlur;

import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Executes the official, unmodified Fiji Directionality plugin without a display. */
public class DirectionalityBatch {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("INPUT_DIRECTORY OUTPUT_DIRECTORY SIGMA");
        }
        Path input = Paths.get(args[0]);
        Path output = Paths.get(args[1]);
        Files.createDirectories(output);
        double sigma = Double.parseDouble(args[2]);
        List<Path> images = new ArrayList<>();
        try (java.util.stream.Stream<Path> files = Files.list(input)) {
            files.filter(p -> p.toString().toLowerCase(Locale.ROOT).endsWith(".png"))
                    .sorted()
                    .forEach(images::add);
        }
        java.lang.reflect.Field version = Directionality_.class.getDeclaredField("VERSION_STR");
        version.setAccessible(true);
        StringBuilder log =
                new StringBuilder(
                        "ImageJ="
                                + IJ.getVersion()
                                + "\nJava="
                                + System.getProperty("java.version")
                                + "\nDirectionality="
                                + version.get(null)
                                + "\nBins=180\nRange=0..180\nGaussianSigma="
                                + sigma
                                + "\n");
        for (Path path : images) {
            ImagePlus source = IJ.openImage(path.toString());
            if (source == null) {
                throw new IOException("Cannot open " + path);
            }
            if (source.getStackSize() != 1 || source.getBitDepth() == 24) {
                throw new IllegalArgumentException("Use single-frame grayscale inputs: " + path);
            }
            ij.process.FloatProcessor processor = source.getProcessor().convertToFloatProcessor();
            if (sigma > 0) {
                new GaussianBlur().blurGaussian(processor, sigma);
            }
            ImagePlus working = new ImagePlus(path.getFileName().toString(), processor);
            String stem = path.getFileName().toString().replaceFirst("\\.png$", "");
            Path folder = output.resolve(stem);
            Files.createDirectories(folder);
            for (int mode = 0; mode < 2; mode++) {
                Directionality_ analyzer = new Directionality_();
                analyzer.setImagePlus(working);
                analyzer.setMethod(
                        mode == 0
                                ? Directionality_.AnalysisMethod.LOCAL_GRADIENT_ORIENTATION
                                : Directionality_.AnalysisMethod.FOURIER_COMPONENTS);
                analyzer.setBinNumber(180);
                analyzer.setBinRange(0, 180);
                analyzer.setBuildOrientationMapFlag(false);
                long start = System.nanoTime();
                analyzer.computeHistograms();
                double[] angles = analyzer.getBins();
                double[] histogram = analyzer.getHistograms().get(0);
                String name = mode == 0 ? "local_gradient" : "fourier_components";
                try (PrintWriter writer =
                        new PrintWriter(Files.newBufferedWriter(folder.resolve(name + ".csv")))) {
                    writer.println("angle_deg,weight");
                    for (int i = 0; i < angles.length; i++) {
                        writer.printf(Locale.US, "%.12g,%.12g%n", angles[i], histogram[i]);
                    }
                }
                double total = 0;
                for (double value : histogram) {
                    total += value;
                }
                if (Double.isFinite(total) && total > 0) {
                    analyzer.fitHistograms();
                    double[] fit = analyzer.getFitAnalysis().get(0);
                    try (PrintWriter writer =
                            new PrintWriter(
                                    Files.newBufferedWriter(folder.resolve(name + "_fit.csv")))) {
                        writer.println("center_deg,std_deg,amount,goodness_of_fit");
                        writer.printf(
                                Locale.US,
                                "%.12g,%.12g,%.12g,%.12g%n",
                                Math.toDegrees(fit[0]),
                                Math.toDegrees(fit[1]),
                                fit[2],
                                fit[3]);
                    }
                }
                log.append(
                        stem
                                + ","
                                + name
                                + ",elapsed_ms="
                                + (System.nanoTime() - start) / 1e6
                                + "\n");
            }
            source.close();
            working.close();
            System.out.println(stem);
        }
        Files.write(
                output.resolve("settings.txt"),
                log.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        System.exit(0);
    }
}
