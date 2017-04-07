## #!/usr/bin/env Rscript

##https://support.bioconductor.org/p/94064/

### Load libraries
suppressPackageStartupMessages(library(optparse))
suppressPackageStartupMessages(library(EBImage))
suppressPackageStartupMessages(library(dplyr))



### Define command line arguments
option_list = list(
  make_option(c("-f", "--file"),
              type="character",
              default=NULL,
              help="The RGB image file as INPUT in [png|tif|jpg] format"),
  make_option(c("-o", "--output"),
              type="character",
              default="./",
              help="The output directory (ODIR); default='./'"),
  make_option(c("-r", "--roi"),
              type="character",
              default=NULL,
              help="The region of interest image file (white indicates ROI)"),
  make_option(c("-t", "--table"),
              type="logical",
              action="store_true",
              default="False",
              help="Boolean switch to enable ODIR/INPUT-table.csv output; default=true"),
  make_option(c("-d", "--dgci"),
              type="logical",
              default="False",
              action="store_true",
              help="Boolean switch to enable ODIR/INPUT-dgci.png output; default=false"),
  make_option(c("-e", "--edge"),
              type="logical",
              default="False",
              action="store_true",
              help="Boolean switch to enable ODIR/INPUT-edge.png output; default=false"),
  make_option(c("-l", "--label"),
              type="logical",
              default="False",
              action="store_true",
              help="Boolean switch to enable ODIR/INPUT-label.png output; default=false")
)
opt_parser = OptionParser(option_list=option_list)
opt = parse_args(opt_parser)


### check if input file is specified
if(is.null(opt$f))
{
  print_help(opt_parser)
  stop("The input file (full filepath) is not specified.")
}


### check if input file is an image file on the basis of its file extension:-
### - png
### - tif
### - jpg
if(!grepl("[.](png|tif|jpg)$", tolower(opt$f)))
{
  print_help(opt_parser)
  stop("The input file is not in one of the following format:  png, tif, jpg")
}



### 1. Read the color image
### 2. Compute the dark green color index (DGCI) image
### 3. Find edges in the DGCI image using sobel operator
### 4. Apply ROIs on the DGCI image and the edge image
### 5. Determine feature vectors from DGCI+ROI and edge+ROI images
i = readImage(opt$f)

dat = imageData(i)
r = as.vector(dat[,,1])
g = as.vector(dat[,,2])
b = as.vector(dat[,,3])
## r = as.vector(channel(i, 'red'))
## g = as.vector(channel(i, 'green'))
## b = as.vector(channel(i, 'blue'))

. = rgb2hsv(r, g, b) %>% t %>% as.data.frame %>% mutate(dgci=(((h-0.1666667)/0.1666667) + (1-s) + (1-v))/3)
dgci = Image(.$dgci, dim=dim(i)[1:2], colormode='gray')
gy = filter2(dgci, matrix(c(1, 0, -1,
                            2, 0, -2,
                            1, 0, -1), nrow=3))
gx = filter2(dgci, matrix(c(1, 2, 1,
                            0, 0, 0,
                            -1, -2, -1), nrow=3))
g = sqrt(gx^2 + gy^2)
edge = thresh(g, 3, 3, .1)


if(!is.null(opt$r) && file.exists(opt$r) && grepl("[.](png|tif|jpg)$", tolower(opt$r)))
{
  roi = readImage(opt$r)
  roi = imageData(roi)[,,1]
}else{
  roi = Image(matrix(1, nrow=dim(i)[1], ncol=dim(i)[2])) 
}
roi = roi > 0
roi = bwlabel(roi)

df = data.frame(d=as.vector(dgci), e=as.vector(edge), roi=as.vector(roi)) %>%
  filter(roi > 0) %>%
  group_by(roi) %>%
  mutate(area=n(), edges=sum(e)) %>%
  ungroup %>%
  group_by(roi, area, edges) %>%
  do({h=hist(.$d, breaks=seq(-.1,3,.1), plot=F);
      data.frame(breaks=paste0("dgci.",h$breaks[-length(h$breaks)]), counts=h$counts)}) %>%
  tidyr::spread(breaks, counts) %>% as.data.frame %>%
  cbind(computeFeatures.moment(roi), computeFeatures.shape(roi))



### 6. Write features as table output
### 7. Write image output to directory

name=gsub("[.]...$", "", basename(opt$f))
if(opt$t == T)
{
    write.table(df, file=paste0(opt$o, name, "-table.csv"), sep=";", dec=".", row.names=F, quote=F)
}


if(opt$d == T)
{
  dgci[roi == 0] = 0
  writeImage(dgci, paste0(opt$o, name, "-dgci.png"))
}

if(opt$e == T)
{
  edge[roi == 0] = 0
  writeImage(edge, paste0(opt$o, name, "-edge.png"))
}

if(opt$l == T)
{
  writeImage(colorLabels(roi), paste0(opt$o, name, "-label.png"))
}





