"""Runs the official plugin JARs with Java 17+ source-file mode."""
from pathlib import Path
import argparse
import hashlib
import json
from urllib.request import urlopen
import os
import subprocess


def main():
    root=Path(__file__).resolve().parent
    for dependency in json.loads((root/'dependencies.json').read_text()):
        target=root/'lib'/dependency['file']
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==dependency['sha256']:
            continue
        target.parent.mkdir(exist_ok=True)
        with urlopen(dependency['source'],timeout=60) as response:
            data=response.read()
        if hashlib.sha256(data).hexdigest()!=dependency['sha256']:
            raise ValueError('Dependency checksum mismatch: '+dependency['file'])
        target.write_bytes(data)
    parser=argparse.ArgumentParser()
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--java',default='java')
    parser.add_argument('--sigma',type=float,default=1.0)
    args=parser.parse_args()
    if not 0<=args.sigma<=5:parser.error('sigma must be in [0,5]')
    subprocess.run([args.java,'-Djava.awt.headless=true','--class-path',str(root/'lib'/'*'),
                    str(root/'DirectionalityBatch.java'),str(args.input.resolve()),str(args.output.resolve()),str(args.sigma)],check=True)

if __name__=='__main__':main()
