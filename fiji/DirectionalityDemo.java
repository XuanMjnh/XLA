import fiji.analyze.directionality.Directionality_;

import ij.IJ;
import ij.ImageJ;
import ij.ImagePlus;
import ij.plugin.filter.GaussianBlur;

import java.awt.Component;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;

import javax.imageio.ImageIO;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;

/** Renders the actual ImageJ/Directionality GUI; never redraws the results in Python. */
public class DirectionalityDemo {
    static void snapshot(Component component, File file) throws Exception {
        BufferedImage image =
                new BufferedImage(
                        component.getWidth(), component.getHeight(), BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = image.createGraphics();
        component.printAll(graphics);
        graphics.dispose();
        ImageIO.write(image, "png", file);
    }

    public static void main(String[] args) throws Exception {
        File output = new File(args[1]);
        output.mkdirs();
        new ImageJ(ImageJ.NO_SHOW);
        ImagePlus source = IJ.openImage(args[0]);
        source.show();
        ij.process.FloatProcessor processor = source.getProcessor().convertToFloatProcessor();
        double sigma = Double.parseDouble(args[2]);
        if (sigma > 0) {
            new GaussianBlur().blurGaussian(processor, sigma);
        }
        ImagePlus working = new ImagePlus(source.getTitle(), processor);
        snapshot(source.getWindow(), new File(output, "imagej_input.png"));
        for (int mode = 0; mode < 2; mode++) {
            Directionality_ analyzer = new Directionality_();
            analyzer.setImagePlus(working);
            analyzer.setMethod(
                    mode == 0
                            ? Directionality_.AnalysisMethod.LOCAL_GRADIENT_ORIENTATION
                            : Directionality_.AnalysisMethod.FOURIER_COMPONENTS);
            analyzer.setBinNumber(180);
            analyzer.setBinRange(0, 180);
            analyzer.computeHistograms();
            analyzer.fitHistograms();
            final JFrame plot = analyzer.plotResults();
            final JFrame fit = analyzer.displayFitAnalysis();
            final String name = mode == 0 ? "local_gradient" : "fourier_components";
            SwingUtilities.invokeAndWait(
                    new Runnable() {
                        public void run() {
                            plot.setVisible(true);
                            fit.setVisible(true);
                        }
                    });
            Thread.sleep(250);
            SwingUtilities.invokeAndWait(
                    new Runnable() {
                        public void run() {
                            try {
                                snapshot(plot, new File(output, name + "_plot.png"));
                                snapshot(fit, new File(output, name + "_fit.png"));
                            } catch (Exception e) {
                                throw new RuntimeException(e);
                            }
                            plot.dispose();
                            fit.dispose();
                        }
                    });
        }
        source.close();
        working.close();
        System.out.println("Rendered actual ImageJ and official plugin windows.");
        System.exit(0);
    }
}
