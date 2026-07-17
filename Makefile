.PHONY: verify test client client-qt5 client-qt6 clean

verify:
	bash scripts/verify.sh

test:
	python3 -m unittest discover -s tests -v

client: client-qt5 client-qt6

client-qt5:
	mkdir -p build/client-qt5
	cd build/client-qt5 && qmake ../../client/card-manager.pro && $(MAKE) -j$$(nproc)

client-qt6:
	mkdir -p build/client-qt6
	cd build/client-qt6 && qmake6 ../../client/card-manager.pro && $(MAKE) -j$$(nproc)

clean:
	rm -rf build .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
