#PBS -S /bin/bash
#PBS -m bae
#PBS -M zongyangli86@gmail.com
#PBS -N stereo_height_10-16
#PBS -l nodes=2:ppn=20
#PBS -l walltime=48:00:00

module purge
module load git mpich gdal2-stack anaconda parallel

source /projects/arpae/sw/pyenv.plantiv/bin/activate

bash /home/zongyang/stereo_height/codes/stereo_height.sh
